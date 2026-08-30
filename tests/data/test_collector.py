"""Integration-style tests for the MarketDataCollector using a stubbed NSE provider."""

from __future__ import annotations

from datetime import date, datetime

from app.config.settings import DataQualityConfig, MarketConfig
from app.data.collectors import MarketDataCollector
from app.data.providers.base import MarketDataProvider, ProviderError
from app.models.time import IST
from tests.fixtures.nse_stub import make_stub_nse_provider

MARKET = MarketConfig(
    timezone="Asia/Kolkata",
    sessions={
        "equity_cash": {
            "name": "cash", "start": "09:15", "end": "15:30", "days": [0, 1, 2, 3, 4],
        }
    },
    instruments=[{"symbol": "NIFTY", "kind": "index"}],
)


class FailingProvider(MarketDataProvider):
    name = "failing"

    def get_quote(self, symbol: str) -> dict:
        raise ProviderError("network down")

    def get_candles(
        self, symbol: str, lookback_days: int = 30, timeframe: str = "1d"
    ) -> list[dict]:
        return []

    def get_option_chain(
        self, symbol: str, expiry_date: datetime | date | None = None
    ) -> dict:
        return {"underlying_symbol": symbol, "timestamp": "", "entries": []}

    def get_futures_data(self, symbol: str) -> dict:
        raise ProviderError("network down")

    def get_market_breadth(self) -> dict:
        return {"timestamp": datetime.now(tz=IST).isoformat(), "advancers": 0, "decliners": 0, "unchanged": 0}

    def get_vix(self) -> dict:
        return {"symbol": "INDIAVIX", "timestamp": datetime.now(tz=IST).isoformat(), "value": 0.0, "change": 0.0}

    def get_fii_dii_data(self) -> dict:
        return {"timestamp": datetime.now(tz=IST).isoformat(), "fii_cash_net": 0.0, "dii_cash_net": 0.0}


class TestCollector:
    def test_builds_snapshot(self):
        collector = MarketDataCollector(make_stub_nse_provider())
        snapshot = collector.collect_snapshot(MARKET, DataQualityConfig(require_bid_ask=False))
        assert snapshot.timestamp.tzinfo is not None
        assert "NIFTY" in snapshot.quotes
        assert "NIFTY" in snapshot.option_chains
        assert snapshot.vix is not None
        assert snapshot.breadth is not None
        assert snapshot.meta["provider"] == "nse"

    def test_snapshot_quality_reported(self):
        collector = MarketDataCollector(make_stub_nse_provider())
        snapshot = collector.collect_snapshot(MARKET, DataQualityConfig())
        quality = snapshot.meta.get("quality", {})
        assert "NIFTY" in quality
        assert quality["NIFTY"]["status"] in ("valid", "warning")

    def test_provider_error_degrades_gracefully(self):
        collector = MarketDataCollector(FailingProvider())
        snapshot = collector.collect_snapshot(
            MARKET, DataQualityConfig(require_bid_ask=False)
        )
        assert "NIFTY" in snapshot.meta["quality"]
        assert snapshot.meta["quality"]["NIFTY"]["status"] == "invalid"
        assert snapshot.breadth is not None
