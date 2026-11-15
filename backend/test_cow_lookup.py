import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import httpx
from .config import Settings
from .cow_lookup import answer
from .feedback_agent import FeedbackAgent
from .store import Store
from .telegram_transport import TelegramClient, TelegramReceiver
from .test_notifications import event, TOKEN


class LookupTests(unittest.TestCase):
    def test_grounded_scores_and_pastures(self):
        for text, values in (
            ("What's cow 718's score and location?", ('Cow 718', '4 / 5', 'North pasture', 'Nov 14, 2026', 'not live GPS')),
            ('Can you tell me the score and location of cow 904', ('Cow 904', 'Estrus behavior', '72 / 100', 'South pasture')),
            ('Where is cow 652?', ('Cow 652', 'not assessed', 'North pasture')),
        ):
            reply, _ = answer(text)
            for value in values:
                self.assertIn(value, reply)

    def test_unknown_and_unobserved_are_not_invented(self):
        self.assertIn("couldn't find cow 632", answer('Where is cow 632?')[0])
        reply, _ = answer('What is cow 341 score and location?')
        self.assertIn('not assessed', reply)
        self.assertIn('No last-seen location', reply)
        self.assertNotIn('Last seen:', reply)

    def test_context_and_clarification(self):
        self.assertIn('Which cow', answer('Where is she?')[0])
        self.assertEqual(answer('718', context_tag='')[1], '718')
        self.assertEqual(answer('Where is she?', context_tag='904')[1], '904')
        self.assertEqual(answer('What about 904?', context_tag='718')[1], '904')
        self.assertEqual(answer('What is her score?', alert_tag='718')[1], '718')
        self.assertEqual(answer('score', context_tag='718')[1], '718')
        self.assertIn('Which cow', answer('Scores for cows 718 and 904?')[0])

    def test_feedback_is_not_a_lookup(self):
        for text in ("She's fine, just resting.", 'yep', 'FALSE cow 718 is fine',
                     'Cow 718 is still limping', '718', 'Record this as a false alarm?'):
            self.assertIsNone(answer(text, context_tag='904'), text)

    def test_missing_snapshot_fails_honestly(self):
        with patch('backend.cow_lookup.DATA', Path('nonexistent-herd-for-test.json')):
            self.assertIn('unavailable', answer('Where is cow 718?')[0])


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = Settings(database=str(Path(self.directory.name) / 'state.sqlite3'), api_token=TOKEN,
                                 transport='telegram', telegram_token='123456:'+'t'*32, telegram_chat_id='12345',
                                 telegram_enabled=True, recipient_opted_in=True)
        self.settings.validate()
        self.store = Store(self.settings)
        self.receiver = TelegramReceiver(self.store)
        self.number = 100

    def tearDown(self):
        self.directory.cleanup()

    def receive(self, text, quoted=None):
        self.number += 1
        message = {'message_id': self.number, 'text': text, 'chat': {'id': 12345, 'type': 'private'},
                   'from': {'id': 12345, 'is_bot': False}}
        if quoted:
            message['reply_to_message'] = {'message_id': quoted}
        return self.receiver.accept({'update_id': self.number, 'message': message})

    def process(self):
        incoming = self.store.claim_inbox()
        self.store.process_inbox(incoming, FeedbackAgent(self.settings))
        return self.store.claim_message()

    def test_demo_alert_then_read_only_question_and_followup(self):
        alert = self.store.ingest(event(), telegram_demo=True)
        initial = self.store.claim_message()
        original_body = initial['body']
        self.store.sent(initial, 'sent', 'tg:123456:12345:50')
        self.receive("What's cow 904's score and location?", quoted=50)
        outgoing = self.process()
        self.assertIn('72 / 100', outgoing['body'])
        self.assertIn('South pasture', outgoing['body'])
        self.assertIsNone(outgoing['alert'])
        self.store.sent(outgoing, 'sent', 'tg:123456:12345:51')
        self.receive('Where is she?', quoted=51)
        outgoing = self.process()
        self.assertIn('Cow 904', outgoing['body'])
        self.assertEqual(self.store.alert(alert['id'])['feedback'], [])
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT body FROM messages WHERE id=?', (initial['id'],)).fetchone()[0], original_body)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM pending').fetchone()[0], 0)
        # A native reply to the original alert overrides the later lookup context.
        self.receive('What is her score?', quoted=50)
        outgoing = self.process()
        self.assertIn('Cow 718', outgoing['body'])

    def test_lookup_works_without_alert_and_survives_restart(self):
        self.receive('Where is cow 718?')
        outgoing = self.process()
        self.store.sent(outgoing, 'sent', 'tg:123456:12345:51')
        self.store = Store(self.settings)
        self.receiver = TelegramReceiver(self.store)
        self.receive('and her score?')
        self.assertIn('4 / 5', self.process()['body'])

    def test_no_cow_clarification_deduplication_and_native_reply(self):
        self.receive('What is the score and location?')
        outgoing = self.process()
        self.assertIn('Which cow', outgoing['body'])
        self.store.sent(outgoing, 'sent', 'tg:123456:12345:51')
        self.receive('718', quoted=51)
        incoming = self.store.claim_inbox()
        agent = MagicMock()
        self.store.process_inbox(incoming, agent)
        self.store.process_inbox(incoming, agent)
        agent.interpret.assert_not_called()
        outgoing = self.store.claim_message()
        calls = []
        def send(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200, json={'ok': True, 'result': {'message_id': 52}})
        with httpx.Client(transport=httpx.MockTransport(send)) as client:
            TelegramClient(self.settings, client).send(outgoing, self.store)
        self.assertEqual(calls[0]['reply_parameters']['message_id'], self.number)
        self.assertIn('Cow 718', calls[0]['text'])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM messages WHERE direction='outgoing'").fetchone()[0], 2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM feedback').fetchone()[0], 0)

    def test_lookup_does_not_confirm_or_erase_a_pending_alert_review(self):
        alert = self.store.ingest(event(), telegram_demo=True)
        initial = self.store.claim_message()
        self.store.sent(initial, 'sent', 'tg:123456:12345:50')
        self.receive("She's fine, just resting.", quoted=50)
        confirmation = self.process()
        self.store.sent(confirmation, 'sent', 'tg:123456:12345:51')
        self.receive('Where is cow 904?')
        lookup = self.process()
        self.store.sent(lookup, 'sent', 'tg:123456:12345:52')
        self.receive('yes', quoted=52)
        self.process()
        self.assertEqual(self.store.alert(alert['id'])['feedback'], [])
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM pending').fetchone()[0], 1)
        self.receive('yep', quoted=51)
        self.process()
        self.assertEqual(self.store.alert(alert['id'])['feedback'][0]['verdict'], 'false_positive')


if __name__ == '__main__':
    unittest.main()
