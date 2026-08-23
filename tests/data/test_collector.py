"""Integration-style tests for the MarketDataCollector using the mock provider."""

from __future__ import annotations

from app.config.settings import DataQualityConfig, MarketConfig
from app.data.collectors import MarketDataCollector
from app.data.providers import MockMarketDataProvider, ProviderError

MARKET = MarketConfig(
    timezone="Asia/Kolkata",
    sessions={
        "equity_cash": {
            "name": "cash", "start": "09:15", "end": "15:30", "days": [0, 1, 2, 3, 4],
        }
    },
    instruments=[{"symbol": "NIFTY", "kind": "index"}],
)


class TestCollector:
    def test_builds_snapshot(self):
        collector = MarketDataCollector(MockMarketDataProvider())
        snapshot = collector.collect_snapshot(MARKET, DataQualityConfig(require_bid_ask=False))
        assert snapshot.timestamp.tzinfo is not None
        assert "NIFTY" in snapshot.quotes
        assert "NIFTY" in snapshot.option_chains
        assert snapshot.vix is not None
        assert snapshot.breadth is not None
        assert snapshot.fii_net_buy is not None
        assert snapshot.meta["provider"] == "mock_replay"

    def test_snapshot_quality_reported(self):
        collector = MarketDataCollector(MockMarketDataProvider())
        snapshot = collector.collect_snapshot(MARKET, DataQualityConfig())
        quality = snapshot.meta.get("quality", {})
        assert "NIFTY" in quality
        assert quality["NIFTY"]["status"] in ("valid", "warning")

    def test_provider_error_degrades_gracefully(self):
        class FailingProvider(MockMarketDataProvider):
            name = "failing"

            def get_quote(self, symbol: str) -> dict:
                raise ProviderError("network down")

        collector = MarketDataCollector(FailingProvider())
        snapshot = collector.collect_snapshot(
            MARKET, DataQualityConfig(require_bid_ask=False)
        )
        assert "NIFTY" in snapshot.meta["quality"]
        assert snapshot.meta["quality"]["NIFTY"]["status"] == "invalid"
        # snapshot still returned and other best-effort fields consistent
        assert snapshot.breadth is not None