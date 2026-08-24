"""Risk, cost, position-size, and expected-value models.

These are quantitative-layer outputs. A sized, positive-EV candidate is still
only a research object: it is not evidence of profitability and is never a
live order.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.time import ensure_ist


class CostBreakdown(BaseModel):
    """Transparent Indian-market cost stack for one simulated round trip."""

    notional_entry: float = Field(ge=0)
    notional_exit: float = Field(ge=0)
    brokerage: float = Field(ge=0)
    stt: float = Field(ge=0)
    gst: float = Field(ge=0)
    exchange_charges: float = Field(ge=0)
    sebi_charges: float = Field(ge=0)
    stamp_duty: float = Field(ge=0)
    slippage: float = Field(ge=0)
    spread: float = Field(ge=0)
    total: float = Field(ge=0)
    formula: str = ""


class PositionSize(BaseModel):
    """Quantity implied by the configured per-trade risk budget.

    ``quantity`` is the number of lots. Total units = quantity * lot_size.
    Quantity is never an arbitrary recommendation: it is floored so that the
    estimated stop-out loss including costs stays within the risk budget.
    """

    quantity: int = Field(ge=0)
    lot_size: int = Field(default=1, ge=1)
    point_value: float = Field(default=1.0, gt=0)
    risk_budget: float = Field(ge=0)
    risk_per_unit: float = Field(ge=0)
    estimated_stop_loss: float = Field(ge=0)
    account_size: float = Field(gt=0)
    risk_per_trade_pct: float = Field(gt=0)

    @property
    def units(self) -> int:
        return self.quantity * self.lot_size


class ExpectedValueResult(BaseModel):
    """Reproducible expected-value breakdown after transaction costs.

    ``probability`` is the candidate prior (uninformed 0.5 unless calibrated).
    Net EV is in account currency (INR when account_size is INR).
    """

    probability: float = Field(ge=0, le=1)
    probability_is_calibrated: bool = False
    gross_win: float
    gross_loss: float
    cost_if_win: float = Field(ge=0)
    cost_if_loss: float = Field(ge=0)
    net_win: float
    net_loss: float
    gross_expected_value: float
    net_expected_value: float
    expectancy_r: float
    risk_reward: float
    formula: str = ""


class RiskState(BaseModel):
    """Mutable paper-trading risk book used by the risk filters."""

    account_size: float = Field(gt=0)
    daily_realized_pnl: float = 0.0
    trades_today: int = Field(default=0, ge=0)
    open_positions: int = Field(default=0, ge=0)
    consecutive_losses: int = Field(default=0, ge=0)
    last_loss_at: datetime | None = None
    storage_available: bool = True

    @model_validator(mode="after")
    def _checks(self) -> "RiskState":
        if self.last_loss_at is not None:
            self.last_loss_at = ensure_ist(self.last_loss_at)
        return self


class RiskAssessment(BaseModel):
    """Pass/fail risk gate for one scored signal."""

    approved: bool
    timestamp: datetime
    symbol: str
    strategy_name: str
    rejection_reasons: list[str] = Field(default_factory=list)
    position_size: PositionSize | None = None
    expected_value: ExpectedValueResult | None = None
    round_trip_cost: CostBreakdown | None = None

    @model_validator(mode="after")
    def _checks(self) -> "RiskAssessment":
        self.timestamp = ensure_ist(self.timestamp)
        return self
