"""Telegram Bot API transport. Tokens and provider error bodies are never logged."""
import json
import logging
import threading
import time
import httpx
from .evidence import asset


class TelegramError(Exception):
    def __init__(self, status=None, retry_after=None):
        self.status = status
        self.retry_after = retry_after
        super().__init__('Telegram request failed; check backend configuration and connectivity')


def provider_id(chat_id, message_id, bot_id):
    return f'tg:{bot_id}:{chat_id}:{message_id}'


class TelegramClient:
    def __init__(self, settings, client=None):
        self.settings = settings
        self.client = client
        # Telegram puts the bot token in the URL. Suppress HTTP client URL logs.
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)

    def call(self, method, payload=None, files=None, timeout=30):
        client = self.client or httpx.Client(timeout=timeout, follow_redirects=False)
        try:
            url = f'https://api.telegram.org/bot{self.settings.telegram_token}/{method}'
            kwargs = {'data': payload, 'files': files} if files else {'json': payload or {}}
            response = client.post(url, **kwargs)
            try:
                data = response.json()
            except (ValueError, TypeError):
                raise TelegramError() from None
            if not isinstance(data, dict) or not data.get('ok'):
                status = data.get('error_code', response.status_code) if isinstance(data, dict) else None
                retry = data.get('parameters', {}).get('retry_after') if isinstance(data, dict) else None
                raise TelegramError(status if type(status) is int else None, retry if type(retry) is int else None)
            return data.get('result')
        except httpx.HTTPError:
            raise TelegramError() from None
        finally:
            if self.client is None:
                client.close()

    def send(self, message, store):
        if not (self.settings.transport == 'telegram' and self.settings.telegram_enabled):
            raise TelegramError(403)
        if message['recipient'] != self.settings.notification_recipient:
            raise TelegramError(403)
        payload = {'chat_id': self.settings.telegram_chat_id, 'protect_content': True}
        # Native replies preserve visible conversation context without alert codes.
        with store.connect() as db:
            incoming = db.execute("SELECT provider_sid FROM messages WHERE recipient=? AND alert=? AND direction='incoming' ORDER BY created DESC,rowid DESC LIMIT 1", (message['recipient'], message['alert'])).fetchone()
        namespace = self.settings.telegram_token.split(':')[0]
        reply_sid = message.get('reply_sid') or (incoming[0] if incoming else None)
        if message['kind'] == 'agent' and reply_sid and reply_sid.startswith(f'tg:{namespace}:{self.settings.telegram_chat_id}:'):
            payload['reply_parameters'] = {'message_id': int(reply_sid.split(':')[-1])}
        evidence_id = None
        if message['kind'] == 'alert' and message['alert']:
            event = store.alert(message['alert'])
            evidence_id = event.get('evidenceId')
        if evidence_id:
            try:
                path = asset(self.settings, evidence_id, simulation=bool(event.get('telegramDemo') and event['source'] == 'simulation'))
            except ValueError:
                raise TelegramError(422) from None
            if path.stat().st_size > 49_000_000:
                raise TelegramError(413)
            # The video is the attachment; caption contains only tag/reason/location.
            upload = dict(payload, caption=message['body'].split('\nVideo:', 1)[0], supports_streaming='true')
            upload['protect_content'] = 'true'
            if 'reply_parameters' in upload:
                upload['reply_parameters'] = json.dumps(upload['reply_parameters'])
            with path.open('rb') as stream:
                result = self.call('sendVideo', upload, files={'video': ('evidence.mp4', stream, 'video/mp4')})
        else:
            result = self.call('sendMessage', dict(payload, text=message['body']))
        if not isinstance(result, dict) or type(result.get('message_id')) is not int or result['message_id'] < 1:
            raise TelegramError()
        # Telegram API success means sent to chat, not delivered/read by rancher.
        return 'sent', provider_id(self.settings.telegram_chat_id, result['message_id'], namespace)


class TelegramReceiver:
    def __init__(self, store, client=None):
        self.store = store
        self.settings = store.settings
        self.client = client or TelegramClient(self.settings)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name='holycow-telegram', daemon=True)

    def accept(self, update):
        if not isinstance(update, dict) or type(update.get('update_id')) is not int or update['update_id'] < 0:
            raise ValueError('Invalid Telegram update')
        message = update.get('message')
        if not isinstance(message, dict):
            return {'ignored': True}
        chat, sender = message.get('chat', {}), message.get('from', {})
        if (not isinstance(chat, dict) or not isinstance(sender, dict) or chat.get('type') != 'private'
                or str(chat.get('id')) != self.settings.telegram_chat_id
                or str(sender.get('id')) != self.settings.telegram_chat_id or sender.get('is_bot')):
            return {'ignored': True}
        body = message.get('text')
        if not isinstance(body, str) or not 1 <= len(body.strip()) <= 1600 or type(message.get('message_id')) is not int or message['message_id'] < 1:
            return {'ignored': True}
        if message.get('external_reply'):
            return {'ignored': True}
        quoted = message.get('reply_to_message')
        reply_to = None
        if quoted is not None:
            if not isinstance(quoted, dict) or type(quoted.get('message_id')) is not int:
                return {'ignored': True}
            with self.store.connect() as db:
                known = db.execute("SELECT id FROM messages WHERE provider_sid=? AND recipient=? AND direction='outgoing'", (provider_id(self.settings.telegram_chat_id, quoted['message_id'], self.settings.telegram_token.split(':')[0]), self.settings.notification_recipient)).fetchone()
            # An unknown quoted message must not fall back to a different cow.
            if not known:
                return {'ignored': True}
            reply_to = known['id']
        return self.store.receive(provider_id(self.settings.telegram_chat_id, message['message_id'], self.settings.telegram_token.split(':')[0]),
                                  self.settings.notification_recipient, body, reply_to)

    def poll_once(self):
        offset = self.store.telegram_offset()
        updates = self.client.call('getUpdates', {'offset': offset, 'timeout': 20, 'limit': 50, 'allowed_updates': ['message']}, timeout=25)
        if not isinstance(updates, list):
            raise TelegramError()
        for update in sorted(updates, key=lambda u: u.get('update_id', -1) if isinstance(u, dict) else -1):
            self.accept(update)
            # Only acknowledge after durable inbox commit (ignored updates included).
            self.store.telegram_checkpoint(update['update_id']+1)
        self.store.telegram_heartbeat()

    def run(self):
        while not self.stop.is_set():
            try:
                self.poll_once()
            except Exception as error:
                logging.getLogger(__name__).warning('Telegram receiver unavailable; inbox offset retained for retry')
                delay = getattr(error, 'retry_after', None)
                self.stop.wait(max(5, min(delay, 300)) if type(delay) is int else 5)

    def start(self):
        self.thread.start()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=27)
