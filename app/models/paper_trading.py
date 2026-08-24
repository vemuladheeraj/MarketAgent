"""Paper-trading domain models.

Tracks the real-time lifecycle of simulated trades:
SIGNAL -> PAPER_ENTRY -> MONITOR -> EXIT -> RESULT
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, Field, model_validator

from app.models.backtesting import BacktestTrade, ExitReason
from app.models.enums import Direction, MarketRegime, TradeStage
from app.models.risk import CostBreakdown, PositionSize
from app.models.time import ensure_ist, now_ist
from app.models.trading import Signal


class PaperPosition(BaseModel):
    """Active or closed paper trading position."""

    position_id: str = Field(default_factory=lambda: f"pos_{uuid.uuid4().hex[:8]}")
    signal_id: str | None = None
    strategy_name: str
    symbol: str
    direction: Direction
    stage: TradeStage = TradeStage.SIGNAL
    planned_entry: float = Field(gt=0)
    simulated_entry: float = Field(gt=0)
    entry_time: datetime
    quantity: int = Field(ge=1, description="Lots")
    lot_size: int = Field(default=1, ge=1)
    point_value: float = Field(default=1.0, gt=0)
    stop_loss: float = Field(gt=0)
    targets: list[float] = Field(default_factory=list)
    current_price: float = Field(gt=0)
    unrealized_pnl: float = 0.0
    mae: float = Field(default=0.0, description="Max adverse excursion in points")
    mfe: float = Field(default=0.0, description="Max favorable excursion in points")
    regime: MarketRegime | None = None
    signal_score: float | None = None
    open_time: datetime
    last_update_time: datetime
    exit_time: datetime | None = None
    exit_price: float | None = None
    exit_reason: ExitReason | None = None
    gross_pnl: float | None = None
    net_pnl: float | None = None
    cost: CostBreakdown | None = None
    r_multiple: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _checks(self) -> "PaperPosition":
        self.entry_time = ensure_ist(self.entry_time)
        self.open_time = ensure_ist(self.open_time)
        self.last_update_time = ensure_ist(self.last_update_time)
        if self.exit_time is not None:
            self.exit_time = ensure_ist(self.exit_time)
        return self

    @property
    def units(self) -> int:
        return self.quantity * self.lot_size

    @property
    def is_open(self) -> bool:
        return self.stage in (TradeStage.SIGNAL, TradeStage.PAPER_ENTRY, TradeStage.MONITOR)

    @property
    def is_closed(self) -> bool:
        return self.stage in (TradeStage.EXIT, TradeStage.RESULT)

    def to_completed_trade(self) -> BacktestTrade:
        """Convert a closed paper position into a BacktestTrade record."""
        if not self.is_closed or self.exit_price is None or self.exit_time is None or self.exit_reason is None:
            raise ValueError("cannot convert open or incomplete paper position to completed trade")
        return BacktestTrade(
            trade_id=self.position_id,
            strategy_name=self.strategy_name,
            symbol=self.symbol,
            direction=self.direction,
            entry_time=self.entry_time,
            exit_time=self.exit_time,
            entry_price=self.simulated_entry,
            exit_price=self.exit_price,
            quantity=self.quantity,
            lot_size=self.lot_size,
            point_value=self.point_value,
            stop_loss=self.stop_loss,
            target_price=self.targets[0] if self.targets else self.simulated_entry,
            exit_reason=self.exit_reason,
            gross_pnl=self.gross_pnl or 0.0,
            net_pnl=self.net_pnl or 0.0,
            cost=self.cost or CostBreakdown(
                notional_entry=0, notional_exit=0, brokerage=0, stt=0, gst=0,
                exchange_charges=0, sebi_charges=0, stamp_duty=0, slippage=0, spread=0, total=0
            ),
            r_multiple=self.r_multiple or 0.0,
            holding_period_bars=0,
            regime=self.regime,
            mae=self.mae,
            mfe=self.mfe,
            signal_score=self.signal_score,
            metadata=self.metadata,
        )


class PaperTradeOrder(BaseModel):
    """Approved order intent destined for simulated execution."""

    order_id: str = Field(default_factory=lambda: f"ord_{uuid.uuid4().hex[:8]}")
    signal: Signal
    position_size: PositionSize
    planned_entry: float
    stop_loss: float
    targets: list[float]
    created_at: datetime = Field(default_factory=now_ist)

    @model_validator(mode="after")
    def _checks(self) -> "PaperTradeOrder":
        self.created_at = ensure_ist(self.created_at)
        return self
