"""Walk-Forward validation and anti-overfitting evaluation engine.

Evaluates strategies across rolling and anchored historical partitions to detect
performance degradation, overfit parameter regimes, and stability across market cycles.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
import math

from app.config.settings import (
    RiskConfig,
    SignalConfig,
    StrategyConfig,
    TransactionCostConfig,
)
from app.models.backtesting import (
    BacktestTrade,
    EquityPoint,
    RobustnessReport,
    StrategyPerformance,
    WalkForwardFoldResult,
    WalkForwardResult,
)
from app.models.candle import MarketCandle
from app.strategies.base.strategy import BaseStrategy
from app.backtesting.engine import BacktestEngine
from app.backtesting.metrics import calculate_performance


class WalkForwardSplitter:
    """Generates non-overlapping, chronological train/test dataset partitions."""

    @staticmethod
    def split_rolling(
        candles: Sequence[MarketCandle],
        *,
        train_bars: int,
        test_bars: int,
        step_bars: int | None = None,
    ) -> list[tuple[list[MarketCandle], list[MarketCandle]]]:
        """Generate rolling sliding window train/test partitions."""
        step = step_bars if step_bars is not None else test_bars
        if train_bars <= 0 or test_bars <= 0 or step <= 0:
            raise ValueError("train_bars, test_bars, and step_bars must be positive")

        n = len(candles)
        splits: list[tuple[list[MarketCandle], list[MarketCandle]]] = []
        start = 0
        while start + train_bars + test_bars <= n:
            train_slice = list(candles[start : start + train_bars])
            test_slice = list(candles[start + train_bars : start + train_bars + test_bars])
            splits.append((train_slice, test_slice))
            start += step

        return splits

    @staticmethod
    def split_anchored(
        candles: Sequence[MarketCandle],
        *,
        initial_train_bars: int,
        test_bars: int,
        step_bars: int | None = None,
    ) -> list[tuple[list[MarketCandle], list[MarketCandle]]]:
        """Generate expanding (anchored) train window with rolling test partitions."""
        step = step_bars if step_bars is not None else test_bars
        if initial_train_bars <= 0 or test_bars <= 0 or step <= 0:
            raise ValueError("initial_train_bars, test_bars, and step_bars must be positive")

        n = len(candles)
        splits: list[tuple[list[MarketCandle], list[MarketCandle]]] = []
        train_end = initial_train_bars
        while train_end + test_bars <= n:
            train_slice = list(candles[0:train_end])
            test_slice = list(candles[train_end : train_end + test_bars])
            splits.append((train_slice, test_slice))
            train_end += step

        return splits


class WalkForwardEngine:
    """Executes multi-fold walk-forward validation and generates robustness reports."""

    def __init__(
        self,
        *,
        strategy: BaseStrategy,
        risk_config: RiskConfig | None = None,
        cost_config: TransactionCostConfig | None = None,
        signal_config: SignalConfig | None = None,
        strategy_config: StrategyConfig | None = None,
        lot_size: int = 1,
        point_value: float = 1.0,
        min_lookback_bars: int = 25,
        max_holding_bars: int | None = None,
        overfit_wfe_threshold: float = 0.5,
        overfit_consistency_threshold: float = 0.5,
    ) -> None:
        self.strategy = strategy
        self.risk_config = risk_config or RiskConfig()
        self.cost_config = cost_config or TransactionCostConfig()
        self.signal_config = signal_config or SignalConfig()
        self.strategy_config = strategy_config or StrategyConfig()
        self.lot_size = lot_size
        self.point_value = point_value
        self.min_lookback_bars = min_lookback_bars
        self.max_holding_bars = max_holding_bars
        self.overfit_wfe_threshold = overfit_wfe_threshold
        self.overfit_consistency_threshold = overfit_consistency_threshold

    def run(
        self,
        candles: Sequence[MarketCandle],
        *,
        train_bars: int,
        test_bars: int,
        step_bars: int | None = None,
        anchored: bool = False,
        initial_capital: float = 1_000_000.0,
    ) -> WalkForwardResult:
        """Execute walk-forward validation across all partitions."""
        if anchored:
            folds = WalkForwardSplitter.split_anchored(
                candles,
                initial_train_bars=train_bars,
                test_bars=test_bars,
                step_bars=step_bars,
            )
        else:
            folds = WalkForwardSplitter.split_rolling(
                candles,
                train_bars=train_bars,
                test_bars=test_bars,
                step_bars=step_bars,
            )

        if not folds:
            raise ValueError(
                f"insufficient candles ({len(candles)}) for train_bars={train_bars} and test_bars={test_bars}"
            )

        symbol = candles[0].symbol
        fold_results: list[WalkForwardFoldResult] = []
        all_train_trades: list[BacktestTrade] = []
        all_test_trades: list[BacktestTrade] = []
        regimes_observed: set[str] = set()

        for fold_idx, (train_candles, test_candles) in enumerate(folds):
            # In-sample backtest
            engine_train = BacktestEngine(
                strategies=[self.strategy],
                risk_config=self.risk_config,
                cost_config=self.cost_config,
                signal_config=self.signal_config,
                strategy_config=self.strategy_config,
                lot_size=self.lot_size,
                point_value=self.point_value,
                min_lookback_bars=self.min_lookback_bars,
                max_holding_bars=self.max_holding_bars,
            )
            res_train = engine_train.run(train_candles, strategy_name=self.strategy.name, initial_capital=initial_capital)

            # Out-of-sample backtest
            # Note: For strict out-of-sample continuity, we seed test backtest with lookback warmup from the end of train
            warmup_needed = min(self.min_lookback_bars, len(train_candles))
            combined_test_candles = list(train_candles[-warmup_needed:]) + list(test_candles)

            engine_test = BacktestEngine(
                strategies=[self.strategy],
                risk_config=self.risk_config,
                cost_config=self.cost_config,
                signal_config=self.signal_config,
                strategy_config=self.strategy_config,
                lot_size=self.lot_size,
                point_value=self.point_value,
                min_lookback_bars=warmup_needed,
                max_holding_bars=self.max_holding_bars,
            )
            res_test_full = engine_test.run(combined_test_candles, strategy_name=self.strategy.name, initial_capital=initial_capital)

            # Only retain trades whose entry timestamp is inside the actual test period
            test_start_ts = test_candles[0].timestamp
            test_trades = [t for t in res_test_full.trades if t.entry_time >= test_start_ts]

            test_metrics, _ = calculate_performance(
                test_trades,
                initial_capital=initial_capital,
                start_time=test_start_ts,
            )

            for t in test_trades:
                if t.regime is not None:
                    regimes_observed.add(t.regime.value)

            all_train_trades.extend(res_train.trades)
            all_test_trades.extend(test_trades)

            # Metrics comparisons
            train_pf = res_train.metrics.profit_factor
            test_pf = test_metrics.profit_factor

            if math.isinf(train_pf) and math.isinf(test_pf):
                if res_train.metrics.expectancy > 0:
                    wfe = test_metrics.expectancy / res_train.metrics.expectancy
                else:
                    wfe = 1.0
            elif math.isinf(train_pf):
                wfe = 0.0
            elif train_pf > 0:
                wfe = test_pf / train_pf if not math.isinf(test_pf) else 1.0
            else:
                wfe = 0.0

            if math.isnan(wfe):
                wfe = 0.0

            train_wr = res_train.metrics.win_rate
            test_wr = test_metrics.win_rate
            win_rate_retention = (test_wr / train_wr) if train_wr > 0 else (1.0 if test_wr == 0 else 0.0)

            # PnL normalized by bar count
            train_pnl_per_bar = res_train.metrics.net_pnl / len(train_candles)
            test_pnl_per_bar = test_metrics.net_pnl / len(test_candles)
            pnl_retention = (test_pnl_per_bar / train_pnl_per_bar) if abs(train_pnl_per_bar) > 1e-6 else 0.0
            if math.isnan(pnl_retention) or math.isinf(pnl_retention):
                pnl_retention = 0.0

            fold_results.append(
                WalkForwardFoldResult(
                    fold_index=fold_idx,
                    train_start=train_candles[0].timestamp,
                    train_end=train_candles[-1].timestamp,
                    test_start=test_candles[0].timestamp,
                    test_end=test_candles[-1].timestamp,
                    train_metrics=res_train.metrics,
                    test_metrics=test_metrics,
                    wfe=round(wfe, 4),
                    win_rate_retention=round(win_rate_retention, 4),
                    pnl_retention=round(pnl_retention, 4),
                )
            )

        # Robustness Summary
        total_folds = len(fold_results)
        profitable_folds = sum(1 for f in fold_results if f.test_metrics.net_pnl > 0)
        consistency_score = profitable_folds / total_folds if total_folds > 0 else 0.0
        avg_wfe = sum(f.wfe for f in fold_results) / total_folds if total_folds > 0 else 0.0
        avg_wr_retention = sum(f.win_rate_retention for f in fold_results) / total_folds if total_folds > 0 else 0.0
        avg_pnl_retention = sum(f.pnl_retention for f in fold_results) / total_folds if total_folds > 0 else 0.0

        is_overfit = (
            avg_wfe < self.overfit_wfe_threshold
            or consistency_score < self.overfit_consistency_threshold
        )

        robustness = RobustnessReport(
            strategy_name=self.strategy.name,
            symbol=symbol,
            total_folds=total_folds,
            profitable_folds=profitable_folds,
            consistency_score=round(consistency_score, 4),
            average_wfe=round(avg_wfe, 4),
            average_win_rate_retention=round(avg_wr_retention, 4),
            average_pnl_retention=round(avg_pnl_retention, 4),
            is_overfit_suspect=is_overfit,
            folds=fold_results,
            regimes_tested=sorted(regimes_observed),
        )

        overall_train_metrics, _ = calculate_performance(all_train_trades, initial_capital=initial_capital)
        overall_test_metrics, test_equity_curve = calculate_performance(
            all_test_trades,
            initial_capital=initial_capital,
            start_time=candles[0].timestamp,
        )

        return WalkForwardResult(
            strategy_name=self.strategy.name,
            symbol=symbol,
            start_time=candles[0].timestamp,
            end_time=candles[-1].timestamp,
            overall_in_sample=overall_train_metrics,
            overall_out_of_sample=overall_test_metrics,
            robustness=robustness,
            out_of_sample_trades=all_test_trades,
            out_of_sample_equity_curve=test_equity_curve,
        )
