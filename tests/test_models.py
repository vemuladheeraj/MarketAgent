"""Unit tests for the core domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.models import (
    DataQuality,
    MarketCandle,
    MarketQuote,
    OptionChainEntry,
    OptionChainSnapshot,
    OptionType,
    SystemEventType,
    ensure_ist,
    now_ist,
)
from app.models.instruments import FutureContract, OptionContract
from app.models.time import TimezoneError


def _aware_ist(*, day: int = 10, hour: int = 10, minute: int = 0) -> datetime:
    return datetime(2025, 1, day, hour, minute, tzinfo=ZoneInfo("Asia/Kolkata"))


# ---------------------------------------------------------------- instruments
class TestInstruments:
    def test_future_contract(self):
        f = FutureContract(
            symbol="NIFTY 25JANFUT",
            name="NIFTY Futures",
            underlying_symbol="NIFTY",
            expiry_date=_aware_ist(day=30, hour=15, minute=30),
            contract_size=75,
            lot_size=75,
        )
        assert f.contract_size == 75
        assert f.lot_size == 75
        assert f.expiry_date.tzinfo is not None

    def test_future_rejects_zero_lot(self):
        with pytest.raises(ValidationError):
            FutureContract(
                symbol="NIFTY 25JANFUT",
                underlying_symbol="NIFTY",
                expiry_date=_aware_ist(day=30, hour=15, minute=30),
                contract_size=0,
                lot_size=0,
            )

    def test_option_contract(self):
        o = OptionContract(
            symbol="NIFTY 24500 CE",
            name="NIFTY Call",
            underlying_symbol="NIFTY",
            expiry_date=_aware_ist(day=30, hour=15, minute=30),
            strike=24500,
            option_type=OptionType.CALL,
            lot_size=75,
        )
        assert o.is_call is True
        assert o.is_put is False
        assert "CE" in o.option_key
        assert o.strike == 24500

    def test_option_contract_rejects_zero_strike(self):
        with pytest.raises(ValidationError):
            OptionContract(
                symbol="NIFTY CE",
                underlying_symbol="NIFTY",
                expiry_date=_aware_ist(day=30, hour=15, minute=30),
                strike=0,
                option_type=OptionType.CALL,
            )

    def test_blank_symbol_rejected(self):
        with pytest.raises(ValidationError):
            OptionContract(
                symbol="   ",
                underlying_symbol="NIFTY",
                expiry_date=_aware_ist(day=30, hour=15, minute=30),
                strike=100,
                option_type=OptionType.PUT,
            )

    def test_naive_expiry_rejected(self):
        with pytest.raises(ValidationError):
            FutureContract(
                symbol="NIFTY FUT",
                underlying_symbol="NIFTY",
                expiry_date=datetime(2025, 1, 30, 15, 30),  # naive
                contract_size=75,
                lot_size=75,
            )


# ---------------------------------------------------------------- candles
class TestMarketCandle:
    def test_valid_candle_roundtrip(self):
        candle = MarketCandle(
            symbol="NIFTY",
            timestamp=_aware_ist(),
            open_price=22000,
            high_price=22100,
            low_price=21990,
            close_price=22050,
            volume=123456,
        )
        assert candle.symbol == "NIFTY"
        assert candle.high_price == 22100

    def test_rejects_naive_timestamp(self):
        with pytest.raises(ValidationError):
            MarketCandle(
                symbol="NIFTY",
                timestamp=datetime(2025, 1, 10, 10, 0),  # naive
                open_price=100,
                high_price=101,
                low_price=99,
                close_price=100,
            )

    def test_rejects_ohlc_violation(self):
        # high is below close -> impossible candle
        with pytest.raises(ValidationError):
            MarketCandle(
                symbol="NIFTY",
                timestamp=_aware_ist(),
                open_price=100,
                high_price=100,
                low_price=95,
                close_price=105,
            )

    def test_rejects_negative_prices(self):
        with pytest.raises(ValidationError):
            MarketCandle(
                symbol="NIFTY",
                timestamp=_aware_ist(),
                open_price=-1,
                high_price=-1,
                low_price=-1,
                close_price=-1,
            )

    def test_volume_defaults_zero(self):
        candle = MarketCandle(
            symbol="NIFTY",
            timestamp=_aware_ist(),
            open_price=100,
            high_price=101,
            low_price=99,
            close_price=100,
        )
        assert candle.volume == 0

    def test_negative_volume_rejected(self):
        with pytest.raises(ValidationError):
            MarketCandle(
                symbol="NIFTY",
                timestamp=_aware_ist(),
                open_price=100,
                high_price=101,
                low_price=99,
                close_price=100,
                volume=-5,
            )

    def test_utc_timestamp_converts(self):
        utc = datetime(2025, 1, 10, 5, 0, tzinfo=timezone.utc)
        candle = MarketCandle(
            symbol="NIFTY",
            timestamp=utc,
            open_price=100,
            high_price=101,
            low_price=99,
            close_price=100,
        )
        assert candle.timestamp.tzinfo is not None
        assert candle.timestamp.hour == 10
        assert candle.timestamp.minute == 30


# ----------------------------------------------------------------- quote
class TestMarketQuote:
    def test_valid_quote(self):
        q = MarketQuote(
            symbol="NIFTY",
            timestamp=_aware_ist(),
            bid=100.5,
            ask=100.7,
            last_price=100.6,
        )
        assert q.bid <= q.ask

    def test_quote_optional_sides(self):
        q = MarketQuote(symbol="NIFTY", timestamp=_aware_ist())
        assert q.bid is None and q.ask is None

    def test_bid_above_ask_rejected(self):
        with pytest.raises(ValidationError):
            MarketQuote(
                symbol="NIFTY",
                timestamp=_aware_ist(),
                bid=101,
                ask=100,
            )


# ------------------------------------------------------------- options chain
def _chain_entry(strike: float, option_type: OptionType) -> OptionChainEntry:
    return OptionChainEntry(
        strike=strike,
        option_type=option_type,
        expiry_date=_aware_ist(day=30, hour=15, minute=30),
        open_interest=1000,
        change_in_oi=100,
        last_price=10.5,
        bid=10.0,
        ask=11.0,
    )


class TestOptionsChain:
    def test_entry_helpers(self):
        call = _chain_entry(24000, OptionType.CALL)
        put = _chain_entry(24000, OptionType.PUT)
        assert call.is_call is True
        assert put.is_put is True

    def test_entry_reconciles_crossed_market(self):
        # Real feeds occasionally emit inverted bid/ask ticks; the model
        # reconciles them (ask clamped to bid) instead of rejecting.
        entry = OptionChainEntry(
            strike=24000,
            option_type=OptionType.CALL,
            expiry_date=_aware_ist(day=30, hour=15, minute=30),
            open_interest=0,
            bid=12.0,
            ask=11.0,
        )
        assert entry.bid == 12.0
        assert entry.ask == 12.0

    def test_snapshot_requires_expiry_after_snapshot(self):
        now = _aware_ist(hour=10)
        with pytest.raises(ValidationError):
            OptionChainSnapshot(
                underlying_symbol="NIFTY",
                timestamp=now,
                spot_price=24000,
                expiry_date=now,  # must be strictly after the snapshot
            )

    def test_pcr_ratio_computed(self):
        ts = _aware_ist()
        snapshot = OptionChainSnapshot(
            underlying_symbol="NIFTY",
            timestamp=ts,
            spot_price=24000,
            expiry_date=_aware_ist(day=30, hour=15, minute=30),
            entries=[
                _chain_entry(24000, OptionType.CALL),
                _chain_entry(24000, OptionType.PUT),
                _chain_entry(24000, OptionType.PUT),
            ],
        )
        assert snapshot.pcr == pytest.approx(2.0)

    def test_pcr_none_when_no_entries(self):
        snapshot = OptionChainSnapshot(
            underlying_symbol="NIFTY",
            timestamp=_aware_ist(),
            spot_price=24000,
            expiry_date=_aware_ist(day=30, hour=15, minute=30),
        )
        assert snapshot.pcr is None


# ------------------------------------------------------------ time helpers
class TestTimeHelpers:
    def test_ensure_ist_converts_utc(self):
        utc = datetime(2025, 1, 10, 5, 0, tzinfo=timezone.utc)
        converted = ensure_ist(utc)
        assert converted.tzinfo == ZoneInfo("Asia/Kolkata")

    def test_ensure_ist_rejects_naive(self):
        with pytest.raises(TimezoneError):
            ensure_ist(datetime(2025, 1, 10, 10, 0))

    def test_now_ist_is_aware(self):
        assert now_ist().tzinfo is not None


# ------------------------------------------------------------- data quality
class TestEnums:
    def test_data_quality_values(self):
        assert DataQuality.VALID.value == "valid"
        assert DataQuality.WARNING.value == "warning"
        assert DataQuality.INVALID.value == "invalid"

    def test_system_event_values(self):
        assert SystemEventType.DATA_RECEIVED.value == "data_received"
        assert SystemEventType.TELEGRAM_ALERT_SENT.value == "telegram_alert_sent"