"""Domain models for backtesting and historical simulation.

These models capture point-in-time trade lifecycles, full Indian transaction
cost breakdowns, equity curve progression, and statistical performance metrics.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.enums import Direction, MarketRegime
from app.models.risk import CostBreakdown
from app.models.time import ensure_ist


class ExitReason(str, enum.Enum):
    """Reason why a simulated trade was exited."""

    TARGET = "target"
    STOP_LOSS = "stop_loss"
    TIME_EXIT = "time_exit"
    INVALIDATION = "invalidation"
    END_OF_DATA = "end_of_data"


class BacktestTrade(BaseModel):
    """Execution record for one closed simulated trade."""

    trade_id: str
    strategy_name: str
    symbol: str
    direction: Direction
    entry_time: datetime
    exit_time: datetime
    entry_price: float = Field(gt=0)
    exit_price: float = Field(gt=0)
    quantity: int = Field(ge=1, description="Number of lots")
    lot_size: int = Field(default=1, ge=1)
    point_value: float = Field(default=1.0, gt=0)
    stop_loss: float = Field(gt=0)
    target_price: float = Field(gt=0)
    exit_reason: ExitReason
    gross_pnl: float
    net_pnl: float
    cost: CostBreakdown
    r_multiple: float
    holding_period_bars: int = Field(ge=0)
    regime: MarketRegime | None = None
    mae: float = Field(default=0.0, description="Max adverse excursion (points)")
    mfe: float = Field(default=0.0, description="Max favorable excursion (points)")
    signal_score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _checks(self) -> "BacktestTrade":
        self.entry_time = ensure_ist(self.entry_time)
        self.exit_time = ensure_ist(self.exit_time)
        if self.exit_time < self.entry_time:
            raise ValueError("exit_time cannot be before entry_time")
        return self

    @property
    def units(self) -> int:
        return self.quantity * self.lot_size

    @property
    def is_win(self) -> bool:
        return self.net_pnl > 0

    @property
    def is_loss(self) -> bool:
        return self.net_pnl < 0


#: Alias for BacktestTrade to satisfy domain requirements
TradeResult = BacktestTrade


class EquityPoint(BaseModel):
    """Snapshot of portfolio equity at a point in time."""

    timestamp: datetime
    gross_equity: float
    net_equity: float
    drawdown_amount: float = Field(default=0.0, ge=0)
    drawdown_pct: float = Field(default=0.0, ge=0, le=100)

    @model_validator(mode="after")
    def _checks(self) -> "EquityPoint":
        self.timestamp = ensure_ist(self.timestamp)
        return self


class StrategyPerformance(BaseModel):
    """Statistical and financial metrics of strategy performance."""

    total_trades: int = Field(ge=0)
    winning_trades: int = Field(ge=0)
    losing_trades: int = Field(ge=0)
    break_even_trades: int = Field(ge=0)
    win_rate: float = Field(ge=0.0, le=1.0)
    gross_pnl: float
    net_pnl: float
    total_costs: float = Field(ge=0.0)
    profit_factor: float = Field(ge=0.0)
    average_trade_net_pnl: float
    average_win: float = Field(ge=0.0)
    average_loss: float = Field(ge=0.0)
    win_loss_ratio: float = Field(ge=0.0)
    average_r: float
    expectancy: float
    max_drawdown_amount: float = Field(ge=0.0)
    max_drawdown_pct: float = Field(ge=0.0, le=100.0)
    sharpe_ratio: float
    sortino_ratio: float
    max_winning_streak: int = Field(ge=0)
    max_losing_streak: int = Field(ge=0)
    trades_by_regime: dict[str, int] = Field(default_factory=dict)
    pnl_by_regime: dict[str, float] = Field(default_factory=dict)


class BacktestResult(BaseModel):
    """Aggregated output from a historical backtest run."""

    backtest_id: str
    strategy_name: str
    symbol: str
    start_time: datetime
    end_time: datetime
    initial_capital: float = Field(gt=0)
    final_capital: float
    metrics: StrategyPerformance
    trades: list[BacktestTrade] = Field(default_factory=list)
    equity_curve: list[EquityPoint] = Field(default_factory=list)
    config_summary: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _checks(self) -> "BacktestResult":
        self.start_time = ensure_ist(self.start_time)
        self.end_time = ensure_ist(self.end_time)
        return self


class WalkForwardFoldResult(BaseModel):
    """Evaluation result for a single train/validation/test fold."""

    fold_index: int = Field(ge=0)
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_metrics: StrategyPerformance
    test_metrics: StrategyPerformance
    wfe: float = Field(description="Walk-forward efficiency (test PF / train PF or test expectancy / train expectancy)")
    win_rate_retention: float = Field(description="test win rate / train win rate")
    pnl_retention: float = Field(description="test net P&L normalized / train net P&L normalized")

    @model_validator(mode="after")
    def _checks(self) -> "WalkForwardFoldResult":
        self.train_start = ensure_ist(self.train_start)
        self.train_end = ensure_ist(self.train_end)
        self.test_start = ensure_ist(self.test_start)
        self.test_end = ensure_ist(self.test_end)
        return self


class RobustnessReport(BaseModel):
    """Overfitting and cross-regime robustness assessment."""

    strategy_name: str
    symbol: str
    total_folds: int = Field(ge=0)
    profitable_folds: int = Field(ge=0)
    consistency_score: float = Field(ge=0.0, le=1.0, description="Fraction of out-of-sample folds with net positive PnL")
    average_wfe: float = Field(description="Average Walk-Forward Efficiency across all folds")
    average_win_rate_retention: float
    average_pnl_retention: float
    is_overfit_suspect: bool = Field(description="True if WFE or consistency falls below safety threshold")
    folds: list[WalkForwardFoldResult] = Field(default_factory=list)
    regimes_tested: list[str] = Field(default_factory=list)


class WalkForwardResult(BaseModel):
    """Complete multi-fold walk-forward validation result."""

    strategy_name: str
    symbol: str
    start_time: datetime
    end_time: datetime
    overall_in_sample: StrategyPerformance
    overall_out_of_sample: StrategyPerformance
    robustness: RobustnessReport
    out_of_sample_trades: list[BacktestTrade] = Field(default_factory=list)
    out_of_sample_equity_curve: list[EquityPoint] = Field(default_factory=list)

