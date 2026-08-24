"""Unit and integration tests for Walk-Forward Validation and Robustness Engine."""

from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from app.config.settings import (
    RiskConfig,
    ScoreBands,
    SignalConfig,
    TransactionCostConfig,
)
from app.models.candle import MarketCandle
from app.models.enums import Direction
from app.models.time import IST
from app.strategies.base.strategy import BaseStrategy, StrategyContext
from app.backtesting.walk_forward import WalkForwardEngine, WalkForwardSplitter

BASE_TIME = datetime(2025, 6, 2, 9, 15, tzinfo=IST)


def _generate_candles(
    count: int = 150,
    *,
    base_price: float = 20000.0,
    price_step: float = 5.0,
) -> list[MarketCandle]:
    candles = []
    current_price = base_price
    for i in range(count):
        ts = BASE_TIME + timedelta(minutes=5 * i)
        open_px = current_price
        close_px = current_price + price_step
        high_px = max(open_px, close_px) + 3.0
        low_px = min(open_px, close_px) - 3.0
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


ALL_FACTORS = {
    "trend": 1.0,
    "momentum": 1.0,
    "price_structure": 1.0,
    "volume": 1.0,
    "oi": 1.0,
    "options_structure": 1.0,
    "volatility": 1.0,
}


class TrendFollowingStrategy(BaseStrategy):
    name = "trend_following_wf"
    preferred_regimes = frozenset()

    def has_setup(self, context: StrategyContext) -> bool:
        # Generates a trade every 10 bars
        return context.technical.sma_20 is not None and context.technical.close > context.technical.sma_20

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        return context.technical.close - 20.0

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        return [context.technical.close + 40.0]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return dict(ALL_FACTORS)


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

PERMISSIVE_RISK = RiskConfig(
    account_size=1_000_000,
    risk_per_trade_pct=1.0,
    min_risk_reward=0.01,
    min_expected_value=-1e9,
)


class TestWalkForwardSplitter:
    def test_rolling_split_partitions(self):
        candles = _generate_candles(100)
        splits = WalkForwardSplitter.split_rolling(
            candles,
            train_bars=40,
            test_bars=20,
            step_bars=20,
        )
        # 100 bars: (0..40, 40..60), (20..60, 60..80), (40..80, 80..100) -> 3 folds
        assert len(splits) == 3
        train0, test0 = splits[0]
        assert len(train0) == 40
        assert len(test0) == 20
        assert train0[-1].timestamp < test0[0].timestamp
        assert test0[-1].timestamp == candles[59].timestamp

    def test_anchored_split_partitions(self):
        candles = _generate_candles(100)
        splits = WalkForwardSplitter.split_anchored(
            candles,
            initial_train_bars=40,
            test_bars=20,
            step_bars=20,
        )
        assert len(splits) == 3
        # fold 0: train 0..40, test 40..60
        # fold 1: train 0..60, test 60..80
        # fold 2: train 0..80, test 80..100
        assert len(splits[0][0]) == 40
        assert len(splits[1][0]) == 60
        assert len(splits[2][0]) == 80


class TestWalkForwardEngine:
    def test_multi_fold_execution(self):
        candles = _generate_candles(120, price_step=3.0)
        strat = TrendFollowingStrategy()

        wf_engine = WalkForwardEngine(
            strategy=strat,
            risk_config=PERMISSIVE_RISK,
            cost_config=ZERO_COSTS,
            signal_config=PERMISSIVE_SIGNAL,
            min_lookback_bars=20,
        )

        wf_result = wf_engine.run(
            candles,
            train_bars=50,
            test_bars=25,
            step_bars=25,
        )

        assert wf_result.strategy_name == strat.name
        assert wf_result.symbol == "NIFTY"
        assert len(wf_result.robustness.folds) == 2  # (0..50, 50..75) and (25..75, 75..100)
        assert wf_result.robustness.total_folds == 2
        assert wf_result.robustness.average_wfe >= 0.0
        assert len(wf_result.out_of_sample_trades) > 0
        assert len(wf_result.out_of_sample_equity_curve) > 0

    def test_insufficient_candles_raises(self):
        candles = _generate_candles(30)
        strat = TrendFollowingStrategy()
        wf_engine = WalkForwardEngine(strategy=strat)
        with pytest.raises(ValueError, match="insufficient candles"):
            wf_engine.run(candles, train_bars=50, test_bars=20)
