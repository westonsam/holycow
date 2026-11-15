import threading
import time
from .feedback_agent import FeedbackAgent


class Sender:
    def __init__(self, settings, store=None):
        self.settings = settings
        self.store = store
        import logging
        logging.getLogger('twilio.http_client').setLevel(logging.WARNING)

    def send(self, message):
        if message['transport'] == 'simulator':
            return 'simulated', 'SIM'+message['id']
        if message['transport'] == 'telegram':
            from .telegram_transport import TelegramClient
            return TelegramClient(self.settings).send(message, self.store)
        if self.settings.transport != 'twilio' or not self.settings.live_enabled:
            raise RuntimeError('Live transport disabled')
        from twilio.rest import Client
        from twilio.http.http_client import TwilioHttpClient
        # No automatic POST retries: a timed-out send may have succeeded.
        client = Client(self.settings.twilio_sid, self.settings.twilio_token,
                        http_client=TwilioHttpClient(timeout=10, max_retries=0))
        response = client.messages.create(
            from_=self.settings.twilio_number, to=message['recipient'], body=message['body'],
            status_callback=f"{self.settings.public_url}/webhooks/twilio/status/{message['id']}",
            validity_period=300,
        )
        return 'accepted', response.sid


class Worker:
    def __init__(self, store, sender=None, agent=None):
        self.store = store
        self.sender = sender or Sender(store.settings, store)
        self.agent = agent or FeedbackAgent(store.settings)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name='holycow-notifications', daemon=True)

    def tick(self):
        self.store.heartbeat()
        incoming = self.store.claim_inbox()
        if incoming:
            try:
                self.store.process_inbox(incoming, self.agent)
            except Exception:
                with self.store.connect() as db:
                    db.execute("UPDATE inbox SET state='queued' WHERE sid=? AND state='processing'", (incoming['sid'],))
                raise
        message = self.store.claim_message()
        if not message:
            return
        try:
            state, sid = self.sender.send(message)
            self.store.sent(message, state, sid)
        except Exception as error:
            status = getattr(error, 'status', None)
            if status == 429 and message['attempts'] < 4:
                self.store.sent(message, 'queued', error='Provider rate limited request; retry scheduled.', retry=True)
                retry_after = getattr(error, 'retry_after', None)
                if type(retry_after) is int and retry_after > 0:
                    with self.store.connect() as db:
                        db.execute('UPDATE messages SET next_attempt=MAX(next_attempt,?) WHERE id=?', (time.time()+retry_after, message['id']))
            elif isinstance(status, int) and 400 <= status < 500:
                self.store.sent(message, 'failed', error='Provider rejected the message. Check sender/recipient configuration.')
            else:
                self.store.sent(message, 'unknown', error='Delivery outcome uncertain. Reconcile with provider; not automatically resent.')

    def run(self):
        while not self.stop.is_set():
            try:
                self.tick()
            except Exception:
                # Do not log bodies, phone numbers, keys or provider exception text.
                import logging
                logging.getLogger(__name__).error('Notification worker tick failed; check service storage availability')
            self.stop.wait(self.store.settings.worker_interval)

    def start(self):
        self.thread.start()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=25)
