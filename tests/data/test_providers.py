"""Tests for the market-data providers (mock) and provider factory."""

from __future__ import annotations

import pytest

from app.config.settings import ProviderConfig
from app.data.providers import (
    MockMarketDataProvider,
    MarketDataProvider,
    ProviderError,
    create_provider,
)


def test_mock_is_registered_and_creatable():
    assert MockMarketDataProvider.name == "mock_replay"
    provider = create_provider(ProviderConfig(name="mock_replay"))
    assert isinstance(provider, MarketDataProvider)
    assert isinstance(provider, MockMarketDataProvider)


def test_create_provider_unknown_name():
    with pytest.raises(ProviderError, match="unknown market-data provider"):
        create_provider(ProviderConfig(name="does_not_exist"))


def test_mock_is_deterministic():
    a = MockMarketDataProvider(seed=42)
    b = MockMarketDataProvider(seed=42)
    assert a.get_quote("NIFTY") == b.get_quote("NIFTY")
    assert a.get_candles("NIFTY", 10) == b.get_candles("NIFTY", 10)


def test_mock_different_seed_differs():
    a = MockMarketDataProvider(seed=1)
    b = MockMarketDataProvider(seed=99)
    assert a.get_vix() != b.get_vix()


class TestMockQuote:
    def test_quote_payload_structure(self):
        q = MockMarketDataProvider().get_quote("NIFTY")
        assert set(["symbol", "timestamp", "bid", "ask", "last_price"]) <= set(q)
        assert q["bid"] <= q["ask"]
        assert q["last_price"] > 0

    def test_quote_unknown_symbol_raises(self):
        with pytest.raises(ProviderError):
            MockMarketDataProvider().get_quote("UNKNOWN")


class TestMockCandles:
    def test_candles_ordered_and_consistent(self):
        candles = MockMarketDataProvider().get_candles("NIFTY", 10)
        assert len(candles) == 10
        timestamps = [c["timestamp"] for c in candles]
        assert timestamps == sorted(timestamps)
        for c in candles:
            assert c["high"] >= c["low"]
            assert c["high"] >= max(c["open"], c["close"])
            assert c["low"] <= min(c["open"], c["close"])
            assert all(v > 0 for v in (c["open"], c["high"], c["low"], c["close"]))


class TestMockChain:
    def test_chain_entries(self):
        chain = MockMarketDataProvider().get_option_chain("NIFTY")
        assert "expiry_date" in chain
        assert len(chain["entries"]) == 22  # 11 strikes x 2 sides
        assert all(e["strike"] > 0 for e in chain["entries"])
        assert {"call", "put"} <= {e["option_type"] for e in chain["entries"]}

    def test_chain_bid_le_ask(self):
        chain = MockMarketDataProvider().get_option_chain("BANKNIFTY")
        for e in chain["entries"]:
            if e["bid"] is not None and e["ask"] is not None:
                assert e["bid"] <= e["ask"]


class TestMockBreadthVixFlows:
    def test_breadth_positive(self):
        b = MockMarketDataProvider().get_market_breadth()
        assert b["advancers"] >= 0 and b["decliners"] >= 0
        assert b["advancers"] + b["decliners"] + b["unchanged"] > 0

    def test_vix_positive(self):
        v = MockMarketDataProvider().get_vix()
        assert v["value"] > 0

    def test_fii_dii_keys(self):
        f = MockMarketDataProvider().get_fii_dii_data()
        assert "fii_cash_net" in f
        assert "dii_cash_net" in f


class TestFuturesPayload:
    def test_futures_contract_fields(self):
        f = MockMarketDataProvider().get_futures_data("NIFTY")
        assert f["contract"]["underlying_symbol"] == "NIFTY"
        assert f["contract"]["lot_size"] > 0
        assert f["quote"]["symbol"] == "NIFTY"