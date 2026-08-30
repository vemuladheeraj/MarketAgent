"""Trade-advisor domain models (the present-moment "companion" layer).

A :class:`TradeBrief` is the human-facing answer to the question *what should
I do right now?*. It fuses the best accepted signal, the risk-engine sizing
and the live option chain into one actionable (or explicitly waiting)
decision-support artifact for a human who executes trades manually.

The system itself never places orders — the brief is advice, not execution.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import DataQuality, Direction, OptionType, SignalClassification
from app.models.time import ensure_ist


class OptionContractRef(BaseModel):
    """The concrete option contract a brief refers to."""

    tradingsymbol: str                       # e.g. "NIFTY 24750 CE"
    strike: float = Field(gt=0)
    option_type: OptionType
    expiry_date: datetime
    last_price: float | None = Field(default=None, gt=0)
    bid: float | None = Field(default=None, ge=0)
    ask: float | None = Field(default=None, ge=0)
    iv: float | None = Field(default=None, ge=0)
    delta: float | None = None
    open_interest: int = Field(default=0, ge=0)
    change_in_oi: int | None = None
    spread_pct: float | None = Field(default=None, ge=0)  # (ask-bid)/mid * 100

    @model_validator(mode="after")
    def _checks(self) -> "OptionContractRef":
        self.expiry_date = ensure_ist(self.expiry_date)
        return self

    @property
    def mid_price(self) -> float | None:
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2.0
        return None


class TradeBrief(BaseModel):
    """Present-moment decision-support brief for one underlying.

    ``action`` semantics:

    * ``BUY``  — buy the referenced option contract now (premium levels).
    * ``SELL`` — reserved for future contract-selling briefs.
    * ``WAIT`` — standing aside is a first-class recommendation; the reason
      is carried in ``waiting_reason``.
    """

    generated_at: datetime
    valid_until: datetime
    action: Literal["BUY", "SELL", "WAIT"]
    underlying_symbol: str
    spot: float | None = Field(default=None, gt=0)
    strategy_name: str = ""
    underlying_direction: Direction | None = None
    contract: OptionContractRef | None = None
    entry: float | None = Field(default=None, gt=0)
    stop_loss: float | None = Field(default=None, gt=0)
    targets: list[float] = Field(default_factory=list)
    risk_reward: float | None = Field(default=None, ge=0)
    lots: int | None = Field(default=None, ge=0)
    lot_size: int = Field(default=1, ge=1)
    risk_amount: float | None = Field(default=None, ge=0)
    target_amount: float | None = Field(default=None, ge=0)
    net_expected_value: float | None = None
    expectancy_r: float | None = None
    probability: float | None = Field(default=None, ge=0, le=1)
    score: float | None = Field(default=None, ge=0, le=100)
    classification: SignalClassification | None = None
    regime: str = ""
    data_quality: DataQuality = DataQuality.VALID
    rationale: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    waiting_reason: str | None = None

    @model_validator(mode="after")
    def _checks(self) -> "TradeBrief":
        self.generated_at = ensure_ist(self.generated_at)
        self.valid_until = ensure_ist(self.valid_until)
        if self.valid_until <= self.generated_at:
            raise ValueError("valid_until must be after generated_at")
        if self.action == "WAIT" and not self.waiting_reason:
            raise ValueError("WAIT briefs must include waiting_reason")
        if self.action != "WAIT":
            if self.contract is None or self.entry is None or self.stop_loss is None:
                raise ValueError("actionable briefs require contract, entry and stop_loss")
            if not self.targets:
                raise ValueError("actionable briefs require at least one target")
            if self.action == "BUY" and self.stop_loss >= self.entry:
                raise ValueError("BUY briefs require stop_loss below entry")
            if self.action == "SELL" and self.stop_loss <= self.entry:
                raise ValueError("SELL briefs require stop_loss above entry")
        return self

    @property
    def is_actionable(self) -> bool:
        return self.action != "WAIT"

    @property
    def setup_key(self) -> str:
        """Stable identity of the setup — used for history dedupe and alerts."""
        if self.contract is None:
            return f"{self.underlying_symbol}|WAIT"
        return "|".join(
            [
                self.underlying_symbol,
                self.strategy_name,
                self.underlying_direction.value if self.underlying_direction else "",
                f"{self.contract.strike:g}",
                self.contract.option_type.value,
                self.contract.expiry_date.strftime("%Y%m%d"),
            ]
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        """True when the brief is older than its validity window."""
        moment = ensure_ist(now) if now is not None else now_ist()
        return moment >= self.valid_until
