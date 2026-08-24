"""Unit and integration tests for BacktestEngine and no-lookahead verification."""

from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from app.analysis.regime.classifier import RegimeAssessment
from app.analysis.technical.engine import TechnicalAnalyzer
from app.config.settings import (
    RiskConfig,
    ScoreBands,
    SignalConfig,
    StrategyConfig,
    TransactionCostConfig,
)
from app.models.backtesting import ExitReason
from app.models.candle import MarketCandle
from app.models.enums import Direction, MarketRegime
from app.models.time import IST
from app.models.trading import StrategyCandidate
from app.risk.costs import TransactionCostModel
from app.strategies.base.strategy import BaseStrategy, StrategyContext
from app.backtesting.engine import BacktestEngine
from app.backtesting.runner import BacktestRunner

BASE_TIME = datetime(2025, 6, 2, 9, 15, tzinfo=IST)

ALL_FACTORS = {
    "trend": 1.0,
    "momentum": 1.0,
    "price_structure": 1.0,
    "volume": 1.0,
    "oi": 1.0,
    "options_structure": 1.0,
    "volatility": 1.0,
}


def _generate_candles(
    count: int = 60,
    *,
    base_price: float = 20000.0,
    price_step: float = 10.0,
    start_time: datetime = BASE_TIME,
) -> list[MarketCandle]:
    """Generate a clean trending series of candles."""
    candles = []
    current_price = base_price
    for i in range(count):
        ts = start_time + timedelta(minutes=5 * i)
        open_px = current_price
        close_px = current_price + price_step
        high_px = max(open_px, close_px) + 5.0
        low_px = min(open_px, close_px) - 5.0
        candles.append(
            MarketCandle(
                symbol="NIFTY",
                timestamp=ts,
                open_price=open_px,
                high_price=high_px,
                low_price=low_px,
                close_price=close_px,
                volume=1000.0,
            )
        )
        current_price = close_px
    return candles


class SimpleAlwaysLongStrategy(BaseStrategy):
    name = "simple_always_long"
    preferred_regimes = frozenset()

    def has_setup(self, context: StrategyContext) -> bool:
        return True

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        return context.technical.close - 50.0

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        return [context.technical.close + 100.0]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return dict(ALL_FACTORS)


class LookaheadAuditStrategy(BaseStrategy):
    """Auditing strategy that verifies no future candles exist when evaluated."""

    name = "lookahead_audit"
    preferred_regimes = frozenset()

    def __init__(self, all_candles: list[MarketCandle]) -> None:
        self.all_candles = all_candles
        self.max_observed_timestamp = None

    def has_setup(self, context: StrategyContext) -> bool:
        eval_ts = context.technical.timestamp
        # Check that we never evaluate with future timestamps
        if self.max_observed_timestamp is not None:
            assert eval_ts > self.max_observed_timestamp, "Timestamps must strictly advance"
        self.max_observed_timestamp = eval_ts

        # Find where this timestamp sits in the entire series
        matching_indices = [
            i for i, c in enumerate(self.all_candles) if c.timestamp == eval_ts
        ]
        assert len(matching_indices) == 1, "Timestamp must be unique"
        curr_idx = matching_indices[0]

        # The technical indicators close price must match exactly the candle at curr_idx
        assert context.technical.close == self.all_candles[curr_idx].close_price
        return True

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        return context.technical.close - 30.0

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        return [context.technical.close + 60.0]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return dict(ALL_FACTORS)


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

PERMISSIVE_SIGNAL = SignalConfig(
    min_signal_score=0.0,
    min_risk_reward=0.01,
    bands=ScoreBands(
        no_trade=0.0,
        weak=0.01,
        watch=0.02,
        valid=0.03,
        high_quality=0.04,
        exceptional=0.05,
    ),
)

PERMISSIVE_RISK = RiskConfig(
    account_size=1_000_000,
    risk_per_trade_pct=1.0,
    min_risk_reward=0.01,
    min_expected_value=-1e9,
)


class TestBacktestEngine:
    def test_zero_lookahead_audit(self):
        """Verify that the engine never exposes future candles to strategy evaluation."""
        candles = _generate_candles(count=50, price_step=5.0)
        audit_strategy = LookaheadAuditStrategy(candles)

        engine = BacktestEngine(
            strategies=[audit_strategy],
            cost_config=ZERO_COSTS,
            signal_config=PERMISSIVE_SIGNAL,
            risk_config=PERMISSIVE_RISK,
            min_lookback_bars=20,
        )

        result = engine.run(candles, strategy_name="lookahead_audit")
        assert audit_strategy.max_observed_timestamp is not None
        assert result.metrics.total_trades >= 1

    def test_long_trade_target_hit(self):
        """Simulate a long setup that hits its target."""
        # 35 bars: 30 bars warmup, bar 30 generates signal, bar 31 enters at open 20150
        # target is entry + 40 = 20190
        # bar 32 surges to High 20250 (hitting target)
        candles = _generate_candles(count=35, base_price=20000.0, price_step=5.0)
        # Modify bar 32 to surge
        surge_bar = MarketCandle(
            symbol="NIFTY",
            timestamp=candles[32].timestamp,
            open_price=candles[31].close_price,
            high_price=20300.0,
            low_price=candles[31].close_price - 2.0,
            close_price=20280.0,
            volume=2000.0,
        )
        candles[32] = surge_bar

        class TargetStrategy(BaseStrategy):
            name = "target_strat"
            preferred_regimes = frozenset()

            def has_setup(self, context: StrategyContext) -> bool:
                # Trigger only on bar 30
                return context.technical.timestamp == candles[30].timestamp

            def calculate_direction(self, context: StrategyContext) -> Direction:
                return Direction.LONG

            def calculate_stop_loss(self, context: StrategyContext) -> float | None:
                return context.technical.close - 50.0

            def calculate_targets(self, context: StrategyContext) -> list[float]:
                return [context.technical.close + 40.0]

            def factor_scores(self, context: StrategyContext) -> dict[str, float]:
                return dict(ALL_FACTORS)

        engine = BacktestEngine(
            strategies=[TargetStrategy()],
            cost_config=ZERO_COSTS,
            signal_config=PERMISSIVE_SIGNAL,
            risk_config=PERMISSIVE_RISK,
            min_lookback_bars=25,
            execution_timing="next_open",
        )

        result = engine.run(candles, strategy_name="target_strat")
        assert result.metrics.total_trades == 1
        trade = result.trades[0]
        assert trade.exit_reason == ExitReason.TARGET
        assert trade.entry_price == candles[31].open_price
        assert trade.exit_price == trade.target_price
        assert trade.net_pnl > 0
        assert trade.is_win

    def test_long_trade_stop_loss_hit(self):
        """Simulate a long setup that gets stopped out."""
        candles = _generate_candles(count=35, base_price=20000.0, price_step=5.0)
        # Bar 32 dumps below stop loss
        dump_bar = MarketCandle(
            symbol="NIFTY",
            timestamp=candles[32].timestamp,
            open_price=candles[31].close_price,
            high_price=candles[31].close_price + 2.0,
            low_price=19800.0,
            close_price=19850.0,
            volume=3000.0,
        )
        candles[32] = dump_bar

        class StopStrategy(BaseStrategy):
            name = "stop_strat"
            preferred_regimes = frozenset()

            def has_setup(self, context: StrategyContext) -> bool:
                return context.technical.timestamp == candles[30].timestamp

            def calculate_direction(self, context: StrategyContext) -> Direction:
                return Direction.LONG

            def calculate_stop_loss(self, context: StrategyContext) -> float | None:
                return context.technical.close - 30.0

            def calculate_targets(self, context: StrategyContext) -> list[float]:
                return [context.technical.close + 60.0]

            def factor_scores(self, context: StrategyContext) -> dict[str, float]:
                return dict(ALL_FACTORS)

        engine = BacktestEngine(
            strategies=[StopStrategy()],
            cost_config=ZERO_COSTS,
            signal_config=PERMISSIVE_SIGNAL,
            risk_config=PERMISSIVE_RISK,
            min_lookback_bars=25,
        )

        result = engine.run(candles, strategy_name="stop_strat")
        assert result.metrics.total_trades == 1
        trade = result.trades[0]
        assert trade.exit_reason == ExitReason.STOP_LOSS
        assert trade.net_pnl < 0
        assert trade.is_loss

    def test_pessimistic_intrabar_clash(self):
        """When both stop-loss and target fall within the bar range, pessimistic mode takes the loss."""
        candles = _generate_candles(count=35, base_price=20000.0, price_step=5.0)
        # Bar 32 has massive expansion breaching both stop 19950 and target 20250
        wild_bar = MarketCandle(
            symbol="NIFTY",
            timestamp=candles[32].timestamp,
            open_price=20150.0,
            high_price=20350.0,
            low_price=19800.0,
            close_price=20200.0,
            volume=5000.0,
        )
        candles[32] = wild_bar

        class ClashStrategy(BaseStrategy):
            name = "clash_strat"
            preferred_regimes = frozenset()

            def has_setup(self, context: StrategyContext) -> bool:
                return context.technical.timestamp == candles[30].timestamp

            def calculate_direction(self, context: StrategyContext) -> Direction:
                return Direction.LONG

            def calculate_stop_loss(self, context: StrategyContext) -> float | None:
                return 19950.0

            def calculate_targets(self, context: StrategyContext) -> list[float]:
                return [20250.0]

            def factor_scores(self, context: StrategyContext) -> dict[str, float]:
                return dict(ALL_FACTORS)

        # 1. Pessimistic exit -> Stop loss
        engine_pessimistic = BacktestEngine(
            strategies=[ClashStrategy()],
            cost_config=ZERO_COSTS,
            signal_config=PERMISSIVE_SIGNAL,
            risk_config=PERMISSIVE_RISK,
            min_lookback_bars=25,
            pessimistic_intrabar_exit=True,
        )
        res_p = engine_pessimistic.run(candles, strategy_name="clash_strat")
        assert res_p.trades[0].exit_reason == ExitReason.STOP_LOSS

        # 2. Optimistic exit -> Target
        engine_optimistic = BacktestEngine(
            strategies=[ClashStrategy()],
            cost_config=ZERO_COSTS,
            signal_config=PERMISSIVE_SIGNAL,
            risk_config=PERMISSIVE_RISK,
            min_lookback_bars=25,
            pessimistic_intrabar_exit=False,
        )
        res_o = engine_optimistic.run(candles, strategy_name="clash_strat")
        assert res_o.trades[0].exit_reason == ExitReason.TARGET

    def test_time_based_exit(self):
        """Test max holding bars exit."""
        candles = _generate_candles(count=45, base_price=20000.0, price_step=1.0)

        class QuietStrategy(BaseStrategy):
            name = "quiet_strat"
            preferred_regimes = frozenset()

            def has_setup(self, context: StrategyContext) -> bool:
                return context.technical.timestamp == candles[30].timestamp

            def calculate_direction(self, context: StrategyContext) -> Direction:
                return Direction.LONG

            def calculate_stop_loss(self, context: StrategyContext) -> float | None:
                return 18000.0  # very wide

            def calculate_targets(self, context: StrategyContext) -> list[float]:
                return [25000.0]  # very wide

            def factor_scores(self, context: StrategyContext) -> dict[str, float]:
                return dict(ALL_FACTORS)

        engine = BacktestEngine(
            strategies=[QuietStrategy()],
            cost_config=ZERO_COSTS,
            signal_config=PERMISSIVE_SIGNAL,
            risk_config=PERMISSIVE_RISK,
            min_lookback_bars=25,
            max_holding_bars=5,
        )
        result = engine.run(candles, strategy_name="quiet_strat")
        assert result.metrics.total_trades == 1
        trade = result.trades[0]
        assert trade.exit_reason == ExitReason.TIME_EXIT
        assert trade.holding_period_bars == 5

    def test_costs_deducted_properly(self):
        """Verify that net PnL equals gross PnL minus transaction costs."""
        candles = _generate_candles(count=35, base_price=20000.0, price_step=5.0)
        # Surge on bar 32
        candles[32] = MarketCandle(
            symbol="NIFTY",
            timestamp=candles[32].timestamp,
            open_price=candles[31].close_price,
            high_price=20300.0,
            low_price=candles[31].close_price - 2.0,
            close_price=20280.0,
            volume=2000.0,
        )

        class ProfitableStrategy(BaseStrategy):
            name = "prof_strat"
            preferred_regimes = frozenset()

            def has_setup(self, context: StrategyContext) -> bool:
                return context.technical.timestamp == candles[30].timestamp

            def calculate_direction(self, context: StrategyContext) -> Direction:
                return Direction.LONG

            def calculate_stop_loss(self, context: StrategyContext) -> float | None:
                return context.technical.close - 50.0

            def calculate_targets(self, context: StrategyContext) -> list[float]:
                return [context.technical.close + 40.0]

            def factor_scores(self, context: StrategyContext) -> dict[str, float]:
                return dict(ALL_FACTORS)

        realistic_cost = TransactionCostConfig(
            brokerage=0.03,
            stt_buy_pct=0.0,
            stt_sell_pct=0.025,
            gst_pct=18.0,
            exchange_charges_pct=0.05,
            sebi_charges_pct=0.0001,
            stamp_duty_pct=0.003,
            slippage_pct=0.05,
            bid_ask_spread_pct=0.02,
        )

        engine = BacktestEngine(
            strategies=[ProfitableStrategy()],
            cost_config=realistic_cost,
            signal_config=PERMISSIVE_SIGNAL,
            risk_config=PERMISSIVE_RISK,
            min_lookback_bars=25,
            lot_size=50,
        )
        res = engine.run(candles, strategy_name="prof_strat")
        assert res.metrics.total_trades == 1
        trade = res.trades[0]
        assert trade.cost.total > 0
        assert round(trade.gross_pnl - trade.cost.total, 4) == trade.net_pnl
        assert res.metrics.net_pnl == trade.net_pnl
        assert res.metrics.total_costs == round(trade.cost.total, 4)

    def test_runner_strategy_comparison(self):
        """Test multi-strategy comparison runner."""
        candles = _generate_candles(count=40, price_step=5.0)
        runner = BacktestRunner(
            strategies=[SimpleAlwaysLongStrategy()],
            cost_config=ZERO_COSTS,
            signal_config=PERMISSIVE_SIGNAL,
            risk_config=PERMISSIVE_RISK,
            min_lookback_bars=25,
        )
        comparison = runner.compare_strategies(candles)
        assert "simple_always_long" in comparison
        table = runner.format_summary_table(comparison)
        assert "simple_always_long" in table
        assert "Trades" in table

    def test_short_trade_target_hit(self):
        """Test short trade lifecycle with target profit."""
        candles = _generate_candles(count=35, base_price=20000.0, price_step=5.0)
        # Bar 32 dumps below short target
        dump_bar = MarketCandle(
            symbol="NIFTY",
            timestamp=candles[32].timestamp,
            open_price=candles[31].close_price,
            high_price=candles[31].close_price + 1.0,
            low_price=20000.0,
            close_price=20020.0,
            volume=3000.0,
        )
        candles[32] = dump_bar

        class ShortStrategy(BaseStrategy):
            name = "short_strat"
            preferred_regimes = frozenset()

            def has_setup(self, context: StrategyContext) -> bool:
                return context.technical.timestamp == candles[30].timestamp

            def calculate_direction(self, context: StrategyContext) -> Direction:
                return Direction.SHORT

            def calculate_stop_loss(self, context: StrategyContext) -> float | None:
                return context.technical.close + 40.0

            def calculate_targets(self, context: StrategyContext) -> list[float]:
                return [context.technical.close - 50.0]

            def factor_scores(self, context: StrategyContext) -> dict[str, float]:
                return dict(ALL_FACTORS)

        engine = BacktestEngine(
            strategies=[ShortStrategy()],
            cost_config=ZERO_COSTS,
            signal_config=PERMISSIVE_SIGNAL,
            risk_config=PERMISSIVE_RISK,
            min_lookback_bars=25,
        )
        res = engine.run(candles, strategy_name="short_strat")
        assert res.metrics.total_trades == 1
        trade = res.trades[0]
        assert trade.direction == Direction.SHORT
        assert trade.exit_reason == ExitReason.TARGET
        assert trade.net_pnl > 0
        assert trade.is_win

    def test_end_of_data_exit(self):
        """Trades left open when candles end should exit with END_OF_DATA."""
        candles = _generate_candles(count=35, base_price=20000.0, price_step=1.0)

        class OpenForeverStrategy(BaseStrategy):
            name = "forever_strat"
            preferred_regimes = frozenset()

            def has_setup(self, context: StrategyContext) -> bool:
                return context.technical.timestamp == candles[30].timestamp

            def calculate_direction(self, context: StrategyContext) -> Direction:
                return Direction.LONG

            def calculate_stop_loss(self, context: StrategyContext) -> float | None:
                return context.technical.close - 50.0

            def calculate_targets(self, context: StrategyContext) -> list[float]:
                return [context.technical.close + 5000.0]  # high target never hit

            def factor_scores(self, context: StrategyContext) -> dict[str, float]:
                return dict(ALL_FACTORS)

        engine = BacktestEngine(
            strategies=[OpenForeverStrategy()],
            cost_config=ZERO_COSTS,
            signal_config=PERMISSIVE_SIGNAL,
            risk_config=PERMISSIVE_RISK,
            min_lookback_bars=25,
            max_holding_bars=None,
        )
        res = engine.run(candles, strategy_name="forever_strat")
        assert res.metrics.total_trades == 1
        trade = res.trades[0]
        assert trade.exit_reason == ExitReason.END_OF_DATA
        assert trade.exit_price == candles[-1].close_price

    def test_invalid_candle_ordering_rejected(self):
        """Engine rejects out-of-order candles to prevent non-chronological replay."""
        candles = _generate_candles(count=30)
        # Swap two candles
        candles[10], candles[11] = candles[11], candles[10]

        engine = BacktestEngine(
            strategies=[SimpleAlwaysLongStrategy()],
            min_lookback_bars=10,
        )
        with pytest.raises(ValueError, match="sorted in ascending chronological order"):
            engine.run(candles)

