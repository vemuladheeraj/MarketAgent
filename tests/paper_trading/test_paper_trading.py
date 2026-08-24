"""Unit tests for Paper Trading Engine and Performance Tracker."""

from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from app.config.settings import (
    FirestoreConfig,
    RiskConfig,
    ScoreBands,
    SignalConfig,
    TransactionCostConfig,
)
from app.models.backtesting import ExitReason
from app.models.candle import MarketCandle, MarketQuote
from app.models.enums import DataQuality, Direction, SignalClassification, TradeStage
from app.models.paper_trading import PaperPosition
from app.models.risk import PositionSize, RiskAssessment, RiskState
from app.models.time import IST
from app.models.trading import Signal, StrategyCandidate
from app.paper_trading.engine import PaperTradingEngine
from app.paper_trading.tracker import PaperPerformanceTracker
from app.risk.costs import TransactionCostModel
from app.storage.market_store import MarketStore

TS = datetime(2025, 6, 27, 9, 15, tzinfo=IST)


def _make_signal(
    *,
    entry: float = 20000.0,
    stop: float = 19950.0,
    target: float = 20100.0,
    direction: Direction = Direction.LONG,
    strategy: str = "orb",
) -> tuple[Signal, RiskAssessment]:
    cand = StrategyCandidate(
        strategy_name=strategy,
        symbol="NIFTY",
        timestamp=TS,
        direction=direction,
        entry=entry,
        stop_loss=stop,
        targets=[target],
        expected_win=abs(target - entry),
        expected_loss=abs(entry - stop),
        expected_value=abs(target - entry) * 0.5 - abs(entry - stop) * 0.5,
        probability=0.5,
    )
    sig = Signal(
        candidate=cand,
        score=85.0,
        classification=SignalClassification.HIGH_QUALITY,
        accepted=True,
        data_quality=DataQuality.VALID,
        timestamp=TS,
    )
    pos_size = PositionSize(
        quantity=2,
        lot_size=50,
        point_value=1.0,
        risk_budget=10000.0,
        risk_per_unit=abs(entry - stop),
        estimated_stop_loss=5000.0,
        account_size=1_000_000.0,
        risk_per_trade_pct=1.0,
    )
    assessment = RiskAssessment(
        approved=True,
        timestamp=TS,
        symbol="NIFTY",
        strategy_name=strategy,
        position_size=pos_size,
    )
    return sig, assessment


ZERO_COSTS = TransactionCostConfig(
    brokerage=0.0,
    stt_buy_pct=0.0,
    stt_sell_pct=0.0,
    gst_pct=0.0,
    exchange_charges_pct=0.0,
    sebi_charges_pct=0.0,
    stamp_duty_pct=0.0,
    slippage_pct=0.0,
    bid_ask_spread_pct=0.0,
)


class TestPaperTradingEngine:
    def _engine(self, costs: TransactionCostConfig | None = None) -> PaperTradingEngine:
        store = MarketStore(FirestoreConfig(project_id=""))
        cost_model = TransactionCostModel(costs or ZERO_COSTS)
        return PaperTradingEngine(store, cost_model, lot_size=50)

    def test_open_position_lifecycle(self):
        engine = self._engine()
        sig, assessment = _make_signal()

        pos = engine.open_position(sig, assessment, execution_price=20002.0)
        assert pos is not None
        assert pos.stage == TradeStage.MONITOR
        assert pos.simulated_entry == 20002.0
        assert pos.quantity == 2
        assert pos.units == 100
        assert len(engine.get_open_positions()) == 1

        # Check store risk state synchronized
        risk_state = engine.store.load_risk_state(1_000_000.0)
        assert risk_state.open_positions == 1
        assert risk_state.trades_today == 1

    def test_risk_rejected_does_not_open(self):
        engine = self._engine()
        sig, assessment = _make_signal()
        assessment.approved = False

        pos = engine.open_position(sig, assessment)
        assert pos is None
        assert len(engine.get_open_positions()) == 0

    def test_quote_updates_unrealized_and_excursion(self):
        engine = self._engine()
        sig, assessment = _make_signal(entry=20000.0, stop=19900.0, target=20200.0)
        pos = engine.open_position(sig, assessment, execution_price=20000.0)

        # Quote ticks up
        q1 = MarketQuote(
            symbol="NIFTY",
            timestamp=TS + timedelta(minutes=1),
            last_price=20050.0,
        )
        closed = engine.update_with_quote(q1)
        assert len(closed) == 0

        active_pos = engine.active_positions[pos.position_id]
        assert active_pos.current_price == 20050.0
        assert active_pos.unrealized_pnl == 50.0 * 100  # 100 units * 50 pts = 5000
        assert active_pos.mfe == 50.0
        assert active_pos.mae == 0.0

        # Quote ticks down
        q2 = MarketQuote(
            symbol="NIFTY",
            timestamp=TS + timedelta(minutes=2),
            last_price=19980.0,
        )
        engine.update_with_quote(q2)
        active_pos = engine.active_positions[pos.position_id]
        assert active_pos.mae == 20.0
        assert active_pos.mfe == 50.0  # retains peak high

    def test_target_exit_on_quote(self):
        engine = self._engine()
        sig, assessment = _make_signal(entry=20000.0, stop=19950.0, target=20100.0)
        pos = engine.open_position(sig, assessment, execution_price=20000.0)

        # Surge hitting target
        q_target = MarketQuote(
            symbol="NIFTY",
            timestamp=TS + timedelta(minutes=5),
            last_price=20105.0,
        )
        closed = engine.update_with_quote(q_target)
        assert len(closed) == 1
        c = closed[0]
        assert c.stage == TradeStage.RESULT
        assert c.exit_reason == ExitReason.TARGET
        assert c.exit_price == 20100.0
        assert c.gross_pnl == 100.0 * 100  # 10,000
        assert c.net_pnl == 10000.0
        assert len(engine.get_open_positions()) == 0

        risk_state = engine.store.load_risk_state(1_000_000.0)
        assert risk_state.open_positions == 0
        assert risk_state.daily_realized_pnl == 10000.0
        assert risk_state.consecutive_losses == 0

    def test_stop_loss_exit_on_quote(self):
        engine = self._engine()
        sig, assessment = _make_signal(entry=20000.0, stop=19950.0, target=20100.0)
        pos = engine.open_position(sig, assessment, execution_price=20000.0)

        # Dump hitting stop
        q_stop = MarketQuote(
            symbol="NIFTY",
            timestamp=TS + timedelta(minutes=5),
            last_price=19940.0,
        )
        closed = engine.update_with_quote(q_stop)
        assert len(closed) == 1
        c = closed[0]
        assert c.exit_reason == ExitReason.STOP_LOSS
        assert c.exit_price == 19950.0
        assert c.net_pnl == -50.0 * 100  # -5000

        risk_state = engine.store.load_risk_state(1_000_000.0)
        assert risk_state.consecutive_losses == 1
        assert risk_state.daily_realized_pnl == -5000.0

    def test_candle_update_intrabar(self):
        engine = self._engine()
        sig, assessment = _make_signal(entry=20000.0, stop=19950.0, target=20100.0)
        pos = engine.open_position(sig, assessment, execution_price=20000.0)

        candle = MarketCandle(
            symbol="NIFTY",
            timestamp=TS + timedelta(minutes=5),
            open_price=20010.0,
            high_price=20120.0,  # exceeds target
            low_price=19990.0,
            close_price=20110.0,
            volume=1000.0,
        )
        closed = engine.update_with_candle(candle)
        assert len(closed) == 1
        assert closed[0].exit_reason == ExitReason.TARGET


class TestPaperPerformanceTracker:
    def test_tracker_evaluation_and_degradation(self):
        engine = PaperTradingEngine(
            MarketStore(FirestoreConfig(project_id="")),
            TransactionCostModel(ZERO_COSTS),
        )
        # Create 5 winning paper trades and 5 losing paper trades
        for i in range(5):
            sig, assessment = _make_signal(strategy="orb", entry=100, stop=90, target=120)
            p = engine.open_position(sig, assessment, execution_price=100)
            engine.close_position(p.position_id, exit_price=120, exit_reason=ExitReason.TARGET)

        for i in range(5):
            sig, assessment = _make_signal(strategy="orb", entry=100, stop=90, target=120)
            p = engine.open_position(sig, assessment, execution_price=100)
            engine.close_position(p.position_id, exit_price=90, exit_reason=ExitReason.STOP_LOSS)

        tracker = PaperPerformanceTracker(initial_capital=100_000.0)
        perf = tracker.evaluate(engine.completed_positions)
        assert perf.total_trades == 10
        assert perf.win_rate == 0.5

        # Check degradation alert if expected win rate was 0.8
        alerts = tracker.check_degradation(
            "orb",
            engine.completed_positions,
            expected_win_rate=0.8,
            expected_profit_factor=2.0,
        )
        assert len(alerts) >= 1
        assert alerts[0].metric == "win_rate"
        assert alerts[0].degradation_pct > 30.0
