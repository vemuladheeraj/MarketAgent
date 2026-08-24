"""Unit and integration tests for Orchestration, Scheduler, and Full Pipeline."""

from __future__ import annotations

from datetime import datetime, time
import pytest

from app.config.settings import MarketConfig, TradingSession
from app.models.enums import DataQuality
from app.models.time import IST
from app.orchestration.runner import MarketAgentApplication
from app.orchestration.scheduler import MarketSessionScheduler

MARKET_CFG = MarketConfig(
    timezone="Asia/Kolkata",
    sessions={
        "equity_cash": TradingSession(start="09:15", end="15:30", days=[0, 1, 2, 3, 4]),
    },
    instruments=[{"symbol": "NIFTY", "name": "NIFTY 50", "kind": "index"}],
)


class TestMarketSessionScheduler:
    def test_market_hours_transitions(self):
        scheduler = MarketSessionScheduler(MARKET_CFG)

        # Monday 09:05 IST -> Pre-Open
        t_pre = datetime(2025, 6, 2, 9, 5, tzinfo=IST)
        assert scheduler.get_session(t_pre) == "pre_open"
        assert scheduler.is_market_open(t_pre)

        # Monday 10:30 IST -> Regular
        t_reg = datetime(2025, 6, 2, 10, 30, tzinfo=IST)
        assert scheduler.get_session(t_reg) == "regular"
        assert scheduler.is_market_open(t_reg)

        # Monday 15:45 IST -> Post-Market
        t_post = datetime(2025, 6, 2, 15, 45, tzinfo=IST)
        assert scheduler.get_session(t_post) == "post_market"
        assert not scheduler.is_market_open(t_post)

        # Monday 20:00 IST -> Closed
        t_night = datetime(2025, 6, 2, 20, 0, tzinfo=IST)
        assert scheduler.get_session(t_night) == "closed"
        assert not scheduler.is_market_open(t_night)

        # Sunday 11:00 IST -> Closed
        t_sun = datetime(2025, 6, 1, 11, 0, tzinfo=IST)
        assert scheduler.get_session(t_sun) == "closed"
        assert not scheduler.is_market_open(t_sun)


class TestMarketIntelligencePipeline:
    def test_full_pipeline_cycle(self, fresh_settings):
        app = MarketAgentApplication(fresh_settings)
        ctx = app.startup()
        assert ctx.pipeline is not None

        cycle_result = app.run_cycle(ctx)
        assert cycle_result is not None
        assert cycle_result.snapshot is not None
        assert cycle_result.data_quality in (DataQuality.VALID, DataQuality.WARNING)
        assert "NIFTY" in cycle_result.technicals
        assert "NIFTY" in cycle_result.regimes
        assert "NIFTY" in cycle_result.gemini_analyses
        assert ctx.store.snapshots.count() >= 1

        app.shutdown()

    def test_daemon_loop_cycles(self, fresh_settings):
        app = MarketAgentApplication(fresh_settings)
        ctx = app.startup()

        # Run 2 quick daemon ticks
        app.run_daemon(ctx, interval_seconds=0.01, max_cycles=2)
        app.shutdown()
        assert not app.is_started()
