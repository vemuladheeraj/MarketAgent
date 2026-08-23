"""Tests for the market-data normalizer."""

from __future__ import annotations

import pytest

from app.data.normalizers import MarketDataNormalizer, NormalizerError
from app.data.providers import MockMarketDataProvider
from app.models import MarketCandle

NORMALIZER = MarketDataNormalizer()


class TestNormalizerQuotes:
    def test_normalize_quote(self):
        raw = MockMarketDataProvider().get_quote("NIFTY")
        quote = NORMALIZER.normalize_quote(raw, "NIFTY")
        assert quote.symbol == "NIFTY"
        assert quote.bid <= quote.ask
        assert quote.timestamp.tzinfo is not None

    def test_normalize_quote_bad_timestamp_raises(self):
        raw = {"symbol": "NIFTY", "timestamp": "not-a-date", "bid": 1, "ask": 2}
        with pytest.raises(NormalizerError):
            NORMALIZER.normalize_quote(raw, "NIFTY")


class TestNormalizerCandles:
    def test_candle_list(self):
        raw = MockMarketDataProvider().get_candles("NIFTY", 5)
        candles = NORMALIZER.normalize_candle_list(raw)
        assert len(candles) == 5
        assert all(isinstance(c, MarketCandle) for c in candles)
        assert all(c.timestamp.tzinfo is not None for c in candles)


class TestNormalizerChain:
    def test_chain(self):
        raw = MockMarketDataProvider().get_option_chain("NIFTY")
        chain = NORMALIZER.normalize_chain(raw)
        assert chain.underlying_symbol == "NIFTY"
        assert len(chain.entries) == 22
        assert chain.entries[0].expiry_date.tzinfo is not None


class TestNormalizerFlows:
    def test_breadth(self):
        b = NORMALIZER.normalize_breadth(
            MockMarketDataProvider().get_market_breadth()
        )
        assert b.total > 0

    def test_fii_dii(self):
        f = NORMALIZER.normalize_fii_dii(
            MockMarketDataProvider().get_fii_dii_data()
        )
        assert f.timestamp.tzinfo is not None

    def test_futures(self):
        f = NORMALIZER.normalize_futures(
            MockMarketDataProvider().get_futures_data("NIFTY")
        )
        assert f.contract.underlying_symbol == "NIFTY"
        assert f.quote.last_price > 0