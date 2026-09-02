from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.data.normalizers.normalizer import NormalizerError
from app.models.enums import OptionType
from app.models.options import OptionChainEntry, OptionChainSnapshot
from app.models.time import ensure_ist


def normalize_us_option_chain(payload: dict[str, Any]) -> OptionChainSnapshot:
    """Normalize a Yahoo Finance-style US option-chain payload into the app domain model."""
    if not isinstance(payload, dict):
        raise NormalizerError("payload must be a dictionary")

    symbol = str(payload.get("underlying_symbol") or payload.get("symbol") or "").upper()
    if not symbol:
        raise NormalizerError("option chain payload is missing underlying_symbol")

    timestamp_raw = payload.get("timestamp") or datetime.utcnow().isoformat() + "Z"
    expiry_raw = payload.get("expiry_date")
    spot_price = float(payload.get("spot_price") or payload.get("last_price") or 0.0)
    if spot_price <= 0:
        raise NormalizerError(f"option chain for {symbol} is missing a valid spot_price")

    try:
        timestamp = _as_datetime(timestamp_raw)
        expiry_date = _as_datetime(expiry_raw)
        timestamp = ensure_ist(_ensure_tz_aware(timestamp))
        expiry_date = ensure_ist(_ensure_tz_aware(expiry_date))
    except (TypeError, ValueError) as exc:
        raise NormalizerError(f"cannot parse US option-chain timestamps for {symbol}: {exc}") from exc

    entries = []
    for row in payload.get("entries", []):
        entries.append(_normalize_entry(row, expiry_date))

    return OptionChainSnapshot(
        underlying_symbol=symbol,
        timestamp=timestamp,
        spot_price=spot_price,
        expiry_date=expiry_date,
        entries=entries,
    )


def _normalize_entry(payload: dict[str, Any], expiry_date: datetime) -> OptionChainEntry:
    option_type_raw = str(payload.get("option_type") or "CALL")
    option_type = OptionType(option_type_raw.strip().lower())
    strike = float(payload.get("strike"))
    return OptionChainEntry(
        strike=strike,
        option_type=option_type,
        expiry_date=expiry_date,
        open_interest=int(payload.get("open_interest", 0) or 0),
        change_in_oi=payload.get("change_in_oi"),
        price_change_pct=payload.get("price_change_pct"),
        last_price=payload.get("last_price"),
        bid=payload.get("bid"),
        ask=payload.get("ask"),
        iv=payload.get("iv"),
        delta=payload.get("delta"),
        gamma=payload.get("gamma"),
        theta=payload.get("theta"),
        vega=payload.get("vega"),
    )


def _as_datetime(value: Any) -> datetime:
    if value is None:
        raise ValueError("datetime value is required")
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    raise TypeError(f"unsupported datetime value: {type(value)!r}")


def _ensure_tz_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=__import__('datetime').timezone.utc)
    return value
