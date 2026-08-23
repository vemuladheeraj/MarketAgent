"""Timezone-aware helpers for Indian market operations.

The application uses timezone-aware datetimes everywhere. IST
(``Asia/Kolkata``) is the canonical timezone for market-facing timestamps.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

UTC = ZoneInfo("UTC")

MARKET_TIMEZONE: ZoneInfo = IST


class TimezoneError(ValueError):
    """Raised when a datetime is naive or uses an unexpected timezone."""


def now_ist() -> datetime:
    """Return the current IST time, tz-aware, with microseconds dropped."""
    return datetime.now(IST).replace(microsecond=0)


def ensure_ist(dt: datetime) -> datetime:
    """Return ``dt`` converted to IST if it is tz-aware.

    Raises :class:`TimezoneError` for naive datetimes — naive timestamps are
    ambiguous and are never accepted by the system.
    """
    _ensure_aware(dt)
    if dt.tzinfo is None:  # pragma: no cover - defensive, _ensure checks first
        raise TimezoneError("naive datetime")
    converted = dt.astimezone(IST)
    return converted


def _ensure_aware(dt: datetime) -> None:
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise TimezoneError(f"naive datetime is not allowed: {dt!r}")