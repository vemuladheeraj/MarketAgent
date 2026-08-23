"""Tests for the market-data validator."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.config.settings import DataQualityConfig, TradingSession
from app.data.normalizers import MarketDataNormalizer
from app.data.providers import MockMarketDataProvider
from app.data.validators import MarketDataValidator
from app.models import MarketCandle, MarketQuote
from app.models.enums import DataQuality
from app.models.time import IST

NORMALIZER = MarketDataNormalizer()
VALIDATOR = MarketDataValidator(DataQualityConfig(max_staleness_seconds=300))


def nowist() -> datetime:
    return datetime(2025, 6, 27, 15, 29, 0, tzinfo=IST)


SESSIONS = {"eq": TradingSession(start="09:15", end="15:30", days=[0, 1, 2, 3, 4])}


def _quote(ts: datetime | None = None) -> MarketQuote:
    raw = MockMarketDataProvider().get_quote("NIFTY")
    q = NORMALIZER.normalize_quote(raw, "NIFTY")
    q.timestamp = ts or nowist()
    return q


def _candle(ts: datetime) -> MarketCandle:
    return MarketCandle(
        symbol="NIFTY", timestamp=ts,
        open_price=100, high_price=101, low_price=99, close_price=100,
    )


class TestQuoteValidator:
    def test_valid_quote(self):
        report = VALIDATOR.validate_quote(_quote(), now=nowist())
        assert report.status == DataQuality.VALID

    def test_stale_quote_warns(self):
        report = VALIDATOR.validate_quote(
            _quote(nowist() - timedelta(minutes=30)), now=nowist())
        assert report.status == DataQuality.WARNING
        assert any(i.code == "stale_quote" for i in report.issues)

    def test_future_quote_invalid(self):
        report = VALIDATOR.validate_quote(
            _quote(nowist() + timedelta(hours=1)), now=nowist())
        assert report.status == DataQuality.INVALID
        assert any(i.code == "future_timestamp" for i in report.issues)

    def test_abnormal_spread_warns(self):
        quote = MarketQuote(symbol="NIFTY", timestamp=nowist(), bid=100, ask=120)
        report = VALIDATOR.validate_quote(quote, now=nowist())
        assert report.status == DataQuality.WARNING
        assert any(i.code == "abnormal_spread" for i in report.issues)


class TestCandleValidator:
    def test_valid_within_session(self):
        report = VALIDATOR.validate_candle(
            _candle(nowist()), now=nowist(), sessions=SESSIONS)
        assert report.status == DataQuality.VALID

    def test_outside_market_hours_warns(self):
        ts = datetime(2025, 6, 28, 20, 0, tzinfo=_now_tz())  # Saturday
        report = VALIDATOR.validate_candle(_candle(ts), now=ts, sessions=SESSIONS)
        assert report.status == DataQuality.WARNING
        assert any(i.code == "outside_market_hours" for i in report.issues)

    def test_duplicate_timestamps_invalid(self):
        candles = [_candle(nowist()), _candle(nowist())]
        report = VALIDATOR.validate_candles(candles, now=nowist())
        assert report.status == DataQuality.INVALID
        assert any(i.code == "duplicate_timestamps" for i in report.issues)


class TestChainValidator:
    def test_valid_chain_no_invalid(self):
        raw = MockMarketDataProvider().get_option_chain("NIFTY")
        chain = NORMALIZER.normalize_chain(raw)
        report = VALIDATOR.validate_chain(chain, now=nowist())
        assert report.status in (DataQuality.VALID, DataQuality.WARNING)
        assert not report.invalid

    def test_expired_chain_invalid(self):
        raw = MockMarketDataProvider().get_option_chain("NIFTY")
        chain = NORMALIZER.normalize_chain(raw)
        chain.timestamp = chain.expiry_date + timedelta(hours=1)
        report = VALIDATOR.validate_chain(chain, now=nowist())
        assert report.status == DataQuality.INVALID
        assert any(i.code == "expired_chain" for i in report.issues)

    def test_empty_chain_warns(self):
        raw = MockMarketDataProvider().get_option_chain("NIFTY")
        chain = NORMALIZER.normalize_chain(raw)
        chain.entries = []
        report = VALIDATOR.validate_chain(chain, now=nowist())
        assert report.status == DataQuality.WARNING


def _now_tz():
    return nowist().tzinfo