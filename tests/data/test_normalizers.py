"""Tests for the market-data normalizer."""

from __future__ import annotations

import pytest

from app.data.normalizers import MarketDataNormalizer, NormalizerError
from app.models import MarketCandle
from tests.fixtures.provider_payloads import (
    sample_breadth,
    sample_candles,
    sample_fii_dii,
    sample_futures,
    sample_option_chain,
    sample_quote,
)

NORMALIZER = MarketDataNormalizer()


class TestNormalizerQuotes:
    def test_normalize_quote(self):
        raw = sample_quote("NIFTY")
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
        raw = sample_candles("NIFTY", 5)
        candles = NORMALIZER.normalize_candle_list(raw)
        assert len(candles) == 5
        assert all(isinstance(c, MarketCandle) for c in candles)
        assert all(c.timestamp.tzinfo is not None for c in candles)


class TestNormalizerChain:
    def test_chain(self):
        raw = sample_option_chain("NIFTY")
        chain = NORMALIZER.normalize_chain(raw)
        assert chain.underlying_symbol == "NIFTY"
        assert len(chain.entries) == 22
        assert chain.entries[0].expiry_date.tzinfo is not None


class TestNormalizerFlows:
    def test_breadth(self):
        b = NORMALIZER.normalize_breadth(sample_breadth())
        assert b.total > 0

    def test_fii_dii(self):
        f = NORMALIZER.normalize_fii_dii(sample_fii_dii())
        assert f.timestamp.tzinfo is not None

    def test_futures(self):
        f = NORMALIZER.normalize_futures(sample_futures("NIFTY"))
        assert f.contract.underlying_symbol == "NIFTY"
        assert f.quote.last_price > 0
