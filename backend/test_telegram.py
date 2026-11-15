from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch
import httpx
from fastapi.testclient import TestClient
from .app import create_app
from .config import Settings
from .delivery import Sender, Worker
from .store import Store
from .telegram_transport import TelegramClient, TelegramError, TelegramReceiver, provider_id
from .test_notifications import event, TOKEN


class TelegramTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = Settings(database=str(Path(self.directory.name)/'telegram.sqlite3'), api_token=TOKEN,
            transport='telegram', telegram_token='123456:'+'t'*32, telegram_chat_id='12345',
            telegram_enabled=True, recipient_opted_in=True)
        self.settings.validate()
        self.store = Store(self.settings)
        self.receiver = TelegramReceiver(self.store)
        self.sequence = 100

    def tearDown(self):
        self.directory.cleanup()

    def live(self, **changes):
        return self.store.ingest(event(source='live', identityBasis='human_verified', locationBasis='human_supplied', **changes))

    def update(self, update_id=1, message_id=200, text="She's fine, just resting.", quoted=None, chat=None, sender=None):
        message = {'message_id':message_id, 'text':text,
                   'chat':chat or {'id':12345, 'type':'private'},
                   'from':sender or {'id':12345, 'is_bot':False}}
        if quoted is not None: message['reply_to_message'] = {'message_id':quoted}
        return {'update_id':update_id, 'message':message}

    def mark_sent(self):
        message = self.store.claim_message()
        self.sequence += 1
        self.store.sent(message, 'sent', provider_id('12345', self.sequence, '123456'))
        return message, self.sequence

    def worker(self):
        sender = MagicMock()
        def send(message):
            self.sequence += 1
            return 'sent', provider_id('12345', self.sequence, '123456')
        sender.send.side_effect = send
        return Worker(self.store, sender=sender)

    def test_fail_closed_configuration(self):
        for settings in (replace(self.settings, telegram_token=''), replace(self.settings, telegram_chat_id='-100'),
                         replace(self.settings, telegram_enabled=False), replace(self.settings, recipient_opted_in=False),
                         replace(self.settings, telegram_updates='unknown'), replace(self.settings, telegram_updates='webhook')):
            with self.assertRaises(ValueError): settings.validate()

    def test_send_text_and_simulator_guard(self):
        alert = self.live()
        message = self.store.claim_message()
        calls = []
        def respond(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200,json={'ok':True,'result':{'message_id':101}})
        with httpx.Client(transport=httpx.MockTransport(respond)) as http:
            result = TelegramClient(self.settings,http).send(message,self.store)
        self.assertEqual(result,('sent','tg:123456:12345:101'))
        self.assertEqual(calls[0]['chat_id'],'12345')
        self.assertEqual(calls[0]['text'],message['body'])
        self.assertNotIn(alert['code'],calls[0]['text'])
        self.assertTrue(calls[0]['protect_content'])
        self.store.sent(message,*result)
        simulated=self.store.ingest(event(eventId='telegram-simulation'))
        with patch('backend.telegram_transport.TelegramClient') as client:
            self.assertEqual(Sender(self.settings,self.store).send(self.store.claim_message())[0],'simulated')
            client.assert_not_called()

    def test_video_upload_caption_is_only_cow_reason_location(self):
        root=Path(self.directory.name)/'evidence'
        root.mkdir()
        (root/'real.mp4').write_bytes(b'video-bytes')
        (root/'manifest.json').write_text(json.dumps({'real-clip':{'file':'real.mp4'}}))
        settings=replace(self.settings,evidence_directory=str(root))
        store=Store(settings)
        alert=store.ingest(event(source='live',identityBasis='registered',locationBasis='recorded',evidenceId='real-clip'))
        requests=[]
        def respond(request):
            requests.append((request.url.path,request.read()))
            return httpx.Response(200,json={'ok':True,'result':{'message_id':102}})
        with httpx.Client(transport=httpx.MockTransport(respond)) as http:
            result=TelegramClient(settings,http).send(store.claim_message(),store)
        self.assertEqual(result[0],'sent')
        self.assertTrue(requests[0][0].endswith('/sendVideo'))
        body=requests[0][1]
        self.assertIn(b'video-bytes',body)
        self.assertIn(b'Cow 718\nReason:',body)
        for secret in (b'\nVideo:',alert['code'].encode(),alert['observedAt'].encode(),b'127.0.0.1'):
            self.assertNotIn(secret,body)

    def test_private_allowlist_and_known_quote(self):
        self.live()
        message,telegram_id=self.mark_sent()
        for update in (self.update(chat={'id':999,'type':'private'}),
                       self.update(sender={'id':999,'is_bot':False}),
                       self.update(chat={'id':12345,'type':'group'}), self.update(quoted=99999)):
            self.assertTrue(self.receiver.accept(update)['ignored'])
        accepted=self.receiver.accept(self.update(quoted=telegram_id))
        self.assertFalse(accepted['duplicate'])
        self.assertTrue(self.receiver.accept(self.update(quoted=telegram_id))['duplicate'])
        with self.store.connect() as db:
            row=db.execute('SELECT * FROM inbox').fetchone()
        self.assertEqual(row['reply_to'],message['id'])
        self.assertEqual(row['body'],"She's fine, just resting.")

    def test_reply_to_older_video_does_not_label_newer_cow(self):
        first=self.live()
        message,first_id=self.mark_sent()
        second=self.live(eventId='newer-cow',cowNumber='904')
        self.mark_sent()
        self.receiver.accept(self.update(quoted=first_id))
        worker=self.worker()
        worker.tick()
        self.receiver.accept(self.update(update_id=2,message_id=201,text='yep'))
        worker.tick()
        self.assertEqual(self.store.alert(first['id'])['feedback'][0]['verdict'],'false_positive')
        self.assertEqual(self.store.alert(second['id'])['feedback'],[])

    def test_native_reply_targets_incoming_telegram_message(self):
        self.live()
        _,telegram_id=self.mark_sent()
        self.receiver.accept(self.update(quoted=telegram_id))
        sender=MagicMock()
        worker=Worker(self.store,sender=sender)
        sender.send.return_value=('sent','tg:123456:12345:999')
        worker.tick()
        outgoing=sender.send.call_args.args[0]
        payloads=[]
        def respond(request):
            payloads.append(json.loads(request.content))
            return httpx.Response(200,json={'ok':True,'result':{'message_id':1000}})
        with httpx.Client(transport=httpx.MockTransport(respond)) as http:
            TelegramClient(self.settings,http).send(outgoing,self.store)
        self.assertEqual(payloads[0]['reply_parameters'],{'message_id':200})

    def test_poll_cursor_is_durable_and_foreign_updates_are_acknowledged(self):
        self.live()
        self.mark_sent()
        client=MagicMock()
        client.call.return_value=[self.update(update_id=40),self.update(update_id=41,message_id=201,chat={'id':999,'type':'private'})]
        receiver=TelegramReceiver(self.store,client)
        receiver.poll_once()
        self.assertEqual(Store(self.settings).telegram_offset(),42)
        receiver.poll_once()
        with self.store.connect() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM inbox').fetchone()[0],1)
        self.assertEqual(client.call.call_args.args[1]['offset'],42)
        other=Store(replace(self.settings,telegram_token='789012:'+'t'*32))
        self.assertEqual(other.telegram_offset(),0)

    def test_poll_does_not_advance_on_storage_failure(self):
        self.live()
        self.mark_sent()
        client=MagicMock()
        client.call.return_value=[self.update(update_id=10)]
        receiver=TelegramReceiver(self.store,client)
        with patch.object(self.store,'receive',side_effect=RuntimeError('database unavailable')):
            with self.assertRaises(RuntimeError): receiver.poll_once()
        self.assertEqual(self.store.telegram_offset(),0)

    def test_start_stop_commands_keep_exact_text_and_acknowledge(self):
        alert=self.live()
        self.receiver.accept(self.update(text='/stop'))
        worker=self.worker()
        worker.tick()
        self.assertEqual(self.store.alert(alert['id'])['state'],'suppressed')
        self.assertTrue(any(m['body']=='Notifications stopped.' and m['state']=='sent' for m in self.store.snapshot()['messages']))
        self.receiver.accept(self.update(update_id=2,message_id=201,text='/start'))
        worker.tick()
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT opted_out FROM subscriptions').fetchone()[0],0)
            self.assertEqual(db.execute("SELECT body FROM inbox WHERE sid='tg:123456:12345:201'").fetchone()[0],'/start')

    def test_webhook_secret_validation_and_deduplication(self):
        settings=replace(self.settings,telegram_updates='webhook',telegram_webhook_secret='s'*40,public_url='https://notifications.example.test')
        app=create_app(settings,start_worker=False)
        with TestClient(app) as client:
            update=self.update(text='/start')
            self.assertEqual(client.post('/webhooks/telegram',json=update).status_code,403)
            headers={'X-Telegram-Bot-Api-Secret-Token':settings.telegram_webhook_secret}
            self.assertEqual(client.post('/webhooks/telegram',json=update,headers=headers).status_code,200)
            self.assertEqual(client.post('/webhooks/telegram',json=update,headers=headers).status_code,200)
            self.assertEqual(client.post('/webhooks/telegram',json={'update_id':'bad'},headers=headers).status_code,400)
            self.assertEqual(client.post('/webhooks/telegram',json=self.update(chat={'id':999,'type':'private'}),headers=headers).status_code,200)
        with app.state.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM inbox').fetchone()[0],1)

    def test_provider_errors_are_sanitized_and_retry_after_is_respected(self):
        self.live()
        def limited(request):
            return httpx.Response(429,json={'ok':False,'error_code':429,'description':self.settings.telegram_token,'parameters':{'retry_after':60}})
        with httpx.Client(transport=httpx.MockTransport(limited)) as http:
            client=TelegramClient(self.settings,http)
            with self.assertRaises(TelegramError) as error: client.call('sendMessage',{})
            self.assertNotIn(self.settings.telegram_token,str(error.exception))
            sender=MagicMock()
            sender.send.side_effect=error.exception
            Worker(self.store,sender=sender).tick()
        message=self.store.snapshot()['messages'][0]
        self.assertEqual(message['state'],'queued')
        with self.store.connect() as db:
            self.assertGreater(db.execute('SELECT next_attempt FROM messages').fetchone()[0],time.time()+50)

    def test_setup_uses_hidden_token_prompt_and_requires_explicit_recipient_choice(self):
        from .telegram_setup import main
        client=MagicMock()
        client.call.side_effect=[{'is_bot':True,'username':'HolyCowTestBot'}, {'url':''},
                                 [self.update(text='/start')]]
        with patch('sys.argv',['setup']), patch('backend.telegram_setup.load_local_env'), \
             patch('backend.telegram_setup.Settings.from_env',return_value=replace(self.settings,telegram_token='')), \
             patch('backend.telegram_setup.getpass',return_value=self.settings.telegram_token) as prompt, \
             patch('backend.telegram_setup.TelegramClient',return_value=client), \
             patch('builtins.input',side_effect=['','1','y']), patch('builtins.print') as output, \
             patch('backend.telegram_setup.save') as save:
            main()
        prompt.assert_called_once()
        values=save.call_args.args[0]
        self.assertEqual(values['HOLYCOW_MESSAGING_TRANSPORT'],'telegram')
        self.assertEqual(values['TELEGRAM_CHAT_ID'],'12345')
        self.assertEqual(values['HOLYCOW_LIVE_TELEGRAM_ENABLED'],'true')
        self.assertNotIn(self.settings.telegram_token,str(output.call_args_list))
        self.assertEqual([call.args[0] for call in client.call.call_args_list],['getMe','getWebhookInfo','getUpdates'])

    def test_setup_preserves_an_existing_webhook_without_confirmation(self):
        from .telegram_setup import main
        client=MagicMock()
        client.call.side_effect=[{'is_bot':True,'username':'HolyCowTestBot'}, {'url':'https://existing.example.test/hook'}]
        with patch('sys.argv',['setup','--action','polling']), patch('backend.telegram_setup.load_local_env'), \
             patch('backend.telegram_setup.Settings.from_env',return_value=self.settings), \
             patch('backend.telegram_setup.TelegramClient',return_value=client), \
             patch('builtins.input',return_value='n'), patch('builtins.print'), patch('backend.telegram_setup.save') as save:
            with self.assertRaises(ValueError): main()
        save.assert_not_called()
        self.assertEqual(client.call.call_count,2)

    def demo_app(self):
        root = Path(self.directory.name)/'evidence'
        root.mkdir(exist_ok=True)
        (root/'demo.mp4').write_bytes(b'test-only-video')
        (root/'manifest.json').write_text(json.dumps({'demo-scene':{'file':'demo.mp4','simulationOnly':True}}))
        return create_app(replace(self.settings,evidence_directory=str(root)),start_worker=False)

    def test_demo_endpoint_is_authenticated_fixed_idempotent_and_throttled(self):
        app = self.demo_app()
        headers = {'Authorization':'Bearer '+TOKEN}
        with TestClient(app) as client:
            self.assertEqual(client.post('/v1/telegram-demo',json={'requestId':'a'*32}).status_code,401)
            self.assertEqual(client.post('/v1/telegram-demo',headers=headers,json={'requestId':'bad'}).status_code,422)
            self.assertEqual(client.post('/v1/telegram-demo',headers=headers,json={'requestId':'a'*32,'recipient':'other'}).status_code,422)
            response = client.post('/v1/telegram-demo',headers=headers,json={'requestId':'a'*32})
            self.assertEqual(response.status_code,200)
            alert = response.json()['data']
            self.assertEqual(alert['source'],'simulation')
            self.assertTrue(alert['telegramDemo'])
            self.assertIn('DEMO ONLY',alert['summary'])
            self.assertEqual(client.post('/v1/telegram-demo',headers=headers,json={'requestId':'a'*32}).json()['data']['id'],alert['id'])
            self.assertEqual(client.post('/v1/telegram-demo',headers=headers,json={'requestId':'b'*32}).status_code,409)
        message = app.state.store.claim_message()
        self.assertEqual(message['transport'],'telegram')
        self.assertEqual(message['recipient'],self.settings.notification_recipient)
        self.assertEqual(message['body'].splitlines()[0],'Cow 718')
        def send(request):
            self.assertTrue(request.url.path.endswith('/sendVideo'))
            self.assertIn(b'DEMO ONLY',request.content)
            self.assertIn(b'test-only-video',request.content)
            self.assertNotIn(b'http://127.0.0.1',request.content)
            return httpx.Response(200,json={'ok':True,'result':{'message_id':700}})
        with httpx.Client(transport=httpx.MockTransport(send)) as http:
            state,sid = TelegramClient(app.state.store.settings,http).send(message,app.state.store)
        app.state.store.sent(message,state,sid)
        receiver = TelegramReceiver(app.state.store)
        receiver.accept(self.update(text="She's fine, just resting.",quoted=700))
        Worker(app.state.store,sender=MagicMock(send=MagicMock(return_value=('sent',provider_id('12345',701,'123456'))))).tick()
        receiver.accept(self.update(update_id=2,message_id=201,text='yep',quoted=701))
        Worker(app.state.store,sender=MagicMock(send=MagicMock(return_value=('sent',provider_id('12345',702,'123456'))))).tick()
        restored = Store(app.state.store.settings)
        self.assertEqual(restored.alert(alert['id'])['feedback'][0]['verdict'],'false_positive')
        self.assertFalse(restored.training_candidates()[0]['eligibleForTraining'])
        self.assertEqual(restored.training_candidates()[0]['source'],'simulation')

    def test_demo_requires_telegram_video_and_active_subscription(self):
        headers = {'Authorization':'Bearer '+TOKEN}
        with TestClient(create_app(replace(self.settings,transport='simulator'),start_worker=False)) as client:
            self.assertEqual(client.post('/v1/telegram-demo',headers=headers,json={'requestId':'a'*32}).status_code,409)
        with TestClient(create_app(replace(self.settings,evidence_directory=str(Path(self.directory.name)/'missing')),start_worker=False)) as client:
            self.assertEqual(client.post('/v1/telegram-demo',headers=headers,json={'requestId':'a'*32}).status_code,409)
        app = self.demo_app()
        with app.state.store.connect() as db:
            db.execute('INSERT INTO subscriptions VALUES (?,1)',(self.settings.notification_recipient,))
        with TestClient(app) as client:
            self.assertEqual(client.post('/v1/telegram-demo',headers=headers,json={'requestId':'a'*32}).status_code,409)
        self.assertEqual(app.state.store.snapshot()['alerts'],[])

    def test_demo_provider_failure_is_saved_without_automatic_resend(self):
        app = self.demo_app()
        with TestClient(app) as client:
            alert = client.post('/v1/telegram-demo',headers={'Authorization':'Bearer '+TOKEN},json={'requestId':'a'*32}).json()['data']
        sender = MagicMock()
        sender.send.side_effect = TelegramError(403)
        worker = Worker(app.state.store,sender=sender)
        worker.tick(); worker.tick()
        self.assertEqual(app.state.store.alert(alert['id'])['state'],'failed')
        sender.send.assert_called_once()


if __name__=='__main__':
    unittest.main()
