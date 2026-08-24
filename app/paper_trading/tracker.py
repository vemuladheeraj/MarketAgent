"""Paper Trading Performance Tracker.

Continuously computes rolling performance metrics for paper trades,
evaluates performance by regime, and flags degradation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.backtesting.metrics import calculate_performance
from app.models.backtesting import StrategyPerformance
from app.models.paper_trading import PaperPosition


class DegradationAlert(BaseModel):
    """Warning emitted when live paper performance falls below backtest expectations."""

    strategy_name: str
    metric: str
    expected_value: float
    actual_value: float
    degradation_pct: float
    message: str


class PaperPerformanceTracker:
    """Computes continuous metrics on closed paper positions."""

    def __init__(self, initial_capital: float = 1_000_000.0) -> None:
        self.initial_capital = initial_capital

    def evaluate(self, positions: list[PaperPosition]) -> StrategyPerformance:
        """Calculate overall performance metrics for completed paper positions."""
        closed = [p.to_completed_trade() for p in positions if p.is_closed]
        metrics, _ = calculate_performance(closed, initial_capital=self.initial_capital)
        return metrics

    def evaluate_recent(
        self,
        positions: list[PaperPosition],
        *,
        last_n_trades: int = 10,
    ) -> StrategyPerformance:
        """Calculate metrics for the most recent N closed paper trades."""
        closed = [p.to_completed_trade() for p in positions if p.is_closed]
        recent = closed[-last_n_trades:] if len(closed) > last_n_trades else closed
        metrics, _ = calculate_performance(recent, initial_capital=self.initial_capital)
        return metrics

    def check_degradation(
        self,
        strategy_name: str,
        positions: list[PaperPosition],
        *,
        expected_win_rate: float,
        expected_profit_factor: float,
        min_trades: int = 5,
        win_rate_tolerance_pct: float = 30.0,
    ) -> list[DegradationAlert]:
        """Compare recent paper results with baseline expectations."""
        strat_positions = [
            p for p in positions if p.strategy_name == strategy_name and p.is_closed
        ]
        if len(strat_positions) < min_trades:
            return []

        recent = self.evaluate_recent(strat_positions, last_n_trades=10)
        alerts: list[DegradationAlert] = []

        if expected_win_rate > 0 and recent.win_rate < expected_win_rate * (1.0 - win_rate_tolerance_pct / 100.0):
            deg = ((expected_win_rate - recent.win_rate) / expected_win_rate) * 100.0
            alerts.append(
                DegradationAlert(
                    strategy_name=strategy_name,
                    metric="win_rate",
                    expected_value=expected_win_rate,
                    actual_value=recent.win_rate,
                    degradation_pct=round(deg, 2),
                    message=f"Paper win rate ({recent.win_rate:.2%}) degraded by {deg:.1f}% below expectation ({expected_win_rate:.2%})",
                )
            )

        if expected_profit_factor > 1.0 and recent.profit_factor < 1.0:
            alerts.append(
                DegradationAlert(
                    strategy_name=strategy_name,
                    metric="profit_factor",
                    expected_value=expected_profit_factor,
                    actual_value=recent.profit_factor,
                    degradation_pct=100.0,
                    message=f"Paper profit factor ({recent.profit_factor:.2f}) dropped below 1.0",
                )
            )

        return alerts
