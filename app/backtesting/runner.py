"""Backtest batch runner and strategy comparison helper.

Facilitates comparing multiple strategies over identical historical data
without lookahead bias, producing structured comparison summaries.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from app.analysis.regime.classifier import RegimeClassifier
from app.analysis.technical.engine import TechnicalAnalyzer
from app.config.settings import (
    RiskConfig,
    SignalConfig,
    StrategyConfig,
    TransactionCostConfig,
)
from app.models.backtesting import BacktestResult
from app.models.candle import MarketCandle
from app.models.options import OptionChainSnapshot
from app.models.options_analysis import OptionMetrics
from app.models.snapshots import BreadthSnapshot
from app.strategies.base.strategy import BaseStrategy
from app.strategies.implementations import default_strategies
from app.backtesting.engine import BacktestEngine


class BacktestRunner:
    """Orchestrates comparative backtests across multiple strategies."""

    def __init__(
        self,
        *,
        strategies: list[BaseStrategy] | None = None,
        risk_config: RiskConfig | None = None,
        cost_config: TransactionCostConfig | None = None,
        signal_config: SignalConfig | None = None,
        strategy_config: StrategyConfig | None = None,
        lot_size: int = 1,
        point_value: float = 1.0,
        min_lookback_bars: int = 30,
        max_holding_bars: int | None = None,
        pessimistic_intrabar_exit: bool = True,
    ) -> None:
        self.strategies = strategies if strategies is not None else default_strategies()
        self.risk_config = risk_config or RiskConfig()
        self.cost_config = cost_config or TransactionCostConfig()
        self.signal_config = signal_config or SignalConfig()
        self.strategy_config = strategy_config or StrategyConfig()
        self.lot_size = lot_size
        self.point_value = point_value
        self.min_lookback_bars = min_lookback_bars
        self.max_holding_bars = max_holding_bars
        self.pessimistic_intrabar_exit = pessimistic_intrabar_exit

    def compare_strategies(
        self,
        candles: Sequence[MarketCandle],
        *,
        option_chains: dict[datetime, OptionChainSnapshot] | None = None,
        option_metrics: dict[datetime, OptionMetrics] | None = None,
        breadth_history: dict[datetime, BreadthSnapshot] | None = None,
        vix_history: dict[datetime, float] | None = None,
        initial_capital: float | None = None,
    ) -> dict[str, BacktestResult]:
        """Run backtests for each enabled strategy individually and compare results."""
        results: dict[str, BacktestResult] = {}
        for strategy in self.strategies:
            engine = BacktestEngine(
                strategies=[strategy],
                risk_config=self.risk_config,
                cost_config=self.cost_config,
                signal_config=self.signal_config,
                strategy_config=self.strategy_config,
                lot_size=self.lot_size,
                point_value=self.point_value,
                min_lookback_bars=self.min_lookback_bars,
                max_holding_bars=self.max_holding_bars,
                pessimistic_intrabar_exit=self.pessimistic_intrabar_exit,
            )
            result = engine.run(
                candles,
                option_chains=option_chains,
                option_metrics=option_metrics,
                breadth_history=breadth_history,
                vix_history=vix_history,
                initial_capital=initial_capital,
                strategy_name=strategy.name,
            )
            results[strategy.name] = result
        return results

    @staticmethod
    def format_summary_table(results: dict[str, BacktestResult]) -> str:
        """Render a readable comparison table of backtest results."""
        header = (
            f"{'Strategy':<32} | {'Trades':<6} | {'Win %':<6} | {'Net P&L':<10} "
            f"| {'Profit Fact':<11} | {'Avg R':<7} | {'Expectancy':<10} | {'Max DD %':<8}"
        )
        sep = "-" * len(header)
        lines = [header, sep]
        for name, res in sorted(results.items()):
            m = res.metrics
            win_pct = f"{m.win_rate * 100:.1f}%"
            pf = "inf" if math_is_inf(m.profit_factor) else f"{m.profit_factor:.2f}"
            line = (
                f"{name:<32} | {m.total_trades:<6} | {win_pct:<6} | {m.net_pnl:<10.2f} "
                f"| {pf:<11} | {m.average_r:<7.2f} | {m.expectancy:<10.2f} | {m.max_drawdown_pct:<7.2f}%"
            )
            lines.append(line)
        return "\n".join(lines)


def math_is_inf(val: float) -> bool:
    import math
    return math.isinf(val)
