from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class AlertInput(StrictModel):
    eventId: str = Field(min_length=8, max_length=100, pattern=r'^[a-zA-Z0-9._:-]+$')
    source: Literal['live', 'simulation']
    severity: Literal['high', 'medium', 'low']
    cowNumber: str = Field(min_length=1, max_length=32, pattern=r'^[a-zA-Z0-9 -]+$')
    identityBasis: Literal['registered', 'human_verified', 'synthetic']
    location: str = Field(min_length=3, max_length=180)
    locationBasis: Literal['recorded', 'human_supplied', 'synthetic']
    summary: str = Field(min_length=10, max_length=600)
    observedAt: str = Field(max_length=40)
    modelVersion: str = Field(min_length=1, max_length=120)
    evidenceId: str | None = Field(default=None, pattern=r'^[a-zA-Z0-9_-]{1,80}$')

    @field_validator('observedAt')
    @classmethod
    def timestamp(cls, value):
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if date.tzinfo is None:
            raise ValueError('Observation time needs a timezone')
        if (date - datetime.now(timezone.utc)).total_seconds() > 300:
            raise ValueError('Observation time cannot be in the future')
        return value

    @field_validator('summary', 'location', 'modelVersion')
    @classmethod
    def text(cls, value):
        if value != value.strip() or any(ord(c) < 32 for c in value) or 'http://' in value.lower() or 'https://' in value.lower():
            raise ValueError('Use plain text without control characters or embedded links')
        return value


class SimulateReply(StrictModel):
    messageId: str = Field(min_length=8, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    body: str = Field(min_length=1, max_length=1600)
    replyToMessageId: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')


class TelegramDemo(StrictModel):
    requestId: str = Field(pattern=r'^[a-f0-9]{32}$')


class Interpretation(StrictModel):
    verdict: Literal['valid', 'false_positive', 'uncertain', 'clarify']
    explanation: str = Field(min_length=1, max_length=300)


class AlertChoice(StrictModel):
    alertId: str | None
