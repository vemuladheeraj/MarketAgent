"""System event and alert models used for observability and notifications."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.enums import SystemEventType
from app.models.time import ensure_ist


class SystemEvent(BaseModel):
    """A single structured observability event."""

    event_type: SystemEventType
    timestamp: datetime
    level: str = "INFO"
    message: str = ""
    source: str = "app"
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _finish(self) -> "SystemEvent":
        self.timestamp = ensure_ist(self.timestamp)
        return self


class Severity(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Alert(BaseModel):
    """A notification message (Telegram alert/digest payload)."""

    title: str
    message: str
    timestamp: datetime
    alert_type: str = "info"  # opening | signal | exit | watch | daily_report | system
    severity: Severity = Severity.INFO
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _finish(self) -> "Alert":
        self.timestamp = ensure_ist(self.timestamp)
        return self