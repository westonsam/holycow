from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    database: str = 'backend/state/notifications.sqlite3'
    api_token: str = ''
    transport: str = 'simulator'
    recipient: str = 'simulated-rancher'
    recipient_opted_in: bool = False
    public_url: str = ''
    twilio_sid: str = ''
    twilio_token: str = ''
    twilio_number: str = ''
    live_enabled: bool = False
    agent_mode: str = 'auto'
    openai_key: str = ''
    openai_model: str = ''
    worker_interval: float = 1
    alert_max_age: int = 3600
    evidence_directory: str = 'backend/evidence'
    telegram_token: str = ''
    telegram_chat_id: str = ''
    telegram_enabled: bool = False
    telegram_updates: str = 'polling'
    telegram_webhook_secret: str = ''

    @classmethod
    def from_env(cls):
        return cls(
            database=os.getenv('HOLYCOW_NOTIFICATIONS_DB', cls.database),
            api_token=os.getenv('HOLYCOW_NOTIFICATIONS_TOKEN', ''),
            transport=os.getenv('HOLYCOW_MESSAGING_TRANSPORT', 'simulator'),
            recipient=os.getenv('HOLYCOW_RANCHER_PHONE', 'simulated-rancher'),
            recipient_opted_in=os.getenv('HOLYCOW_RECIPIENT_OPTED_IN') == 'true',
            public_url=os.getenv('HOLYCOW_PUBLIC_BACKEND_URL', '').rstrip('/'),
            twilio_sid=os.getenv('TWILIO_ACCOUNT_SID', ''),
            twilio_token=os.getenv('TWILIO_AUTH_TOKEN', ''),
            twilio_number=os.getenv('TWILIO_FROM_NUMBER', ''),
            live_enabled=os.getenv('HOLYCOW_LIVE_SMS_ENABLED') == 'true',
            agent_mode=os.getenv('HOLYCOW_FEEDBACK_AGENT', 'auto'),
            openai_key=os.getenv('OPENAI_API_KEY', ''),
            openai_model=os.getenv('HOLYCOW_FEEDBACK_MODEL', ''),
            evidence_directory=os.getenv('HOLYCOW_EVIDENCE_DIRECTORY', 'backend/evidence'),
            telegram_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            telegram_chat_id=os.getenv('TELEGRAM_CHAT_ID', ''),
            telegram_enabled=os.getenv('HOLYCOW_LIVE_TELEGRAM_ENABLED') == 'true',
            telegram_updates=os.getenv('TELEGRAM_UPDATES_MODE', 'polling'),
            telegram_webhook_secret=os.getenv('TELEGRAM_WEBHOOK_SECRET', ''),
        )

    def validate(self):
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]{32,}', self.api_token) or self.api_token.startswith('replace-with-'):
            raise ValueError('Set HOLYCOW_NOTIFICATIONS_TOKEN to a random secret of at least 32 characters')
        if self.transport not in ('simulator', 'twilio', 'telegram') or self.agent_mode not in ('commands', 'openai', 'auto'):
            raise ValueError('Unsupported messaging transport or agent mode')
        if self.agent_mode == 'openai' and not (self.openai_key and self.openai_model):
            raise ValueError('OpenAI feedback requires OPENAI_API_KEY and HOLYCOW_FEEDBACK_MODEL')
        if self.transport == 'telegram':
            if not (self.telegram_enabled and self.recipient_opted_in):
                raise ValueError('Telegram requires explicit enablement and an opted-in recipient')
            if not re.fullmatch(r'\d{5,20}:[A-Za-z0-9_-]{20,}', self.telegram_token):
                raise ValueError('Configure TELEGRAM_BOT_TOKEN in the backend environment')
            if not re.fullmatch(r'[1-9]\d{0,19}', self.telegram_chat_id):
                raise ValueError('Configure the rancher private TELEGRAM_CHAT_ID')
            if self.telegram_updates not in ('polling', 'webhook'):
                raise ValueError('TELEGRAM_UPDATES_MODE must be polling or webhook')
            if self.telegram_updates == 'webhook' and not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', self.telegram_webhook_secret):
                raise ValueError('Configure a random TELEGRAM_WEBHOOK_SECRET for webhook mode')
            if self.telegram_updates == 'webhook':
                url = urlparse(self.public_url)
                if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
                    raise ValueError('Telegram webhook mode requires a public HTTPS backend origin')
        if self.transport == 'twilio':
            url = urlparse(self.public_url)
            if not (self.live_enabled and self.recipient_opted_in and self.twilio_sid and self.twilio_token):
                raise ValueError('Live SMS requires explicit enablement, opted-in recipient and Twilio credentials')
            if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
                raise ValueError('Twilio requires an HTTPS public backend origin')
            if not all(re.fullmatch(r'\+[1-9]\d{7,14}', number) for number in (self.recipient, self.twilio_number)):
                raise ValueError('Set valid E.164 sender and recipient phone numbers')
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)

    @property
    def uses_llm(self):
        return self.agent_mode == 'openai' or (self.agent_mode == 'auto' and bool(self.openai_key and self.openai_model))

    @property
    def notification_recipient(self):
        return 'telegram:'+self.telegram_chat_id if self.transport == 'telegram' else self.recipient
