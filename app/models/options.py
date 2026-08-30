"""Options-chain and option-position domain models.

OI (open interest), PCR, IV and Greek values are only ever filled by the
options-analysis layer (Phase 5). At construction time they are optional.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import OptionType
from app.models.time import ensure_ist


class OptionChainEntry(BaseModel):
    """One strike row of an option chain."""

    strike: float = Field(gt=0)
    option_type: OptionType
    expiry_date: datetime
    open_interest: int = Field(default=0, ge=0)
    change_in_oi: int | None = None
    price_change_pct: float | None = None
    last_price: float | None = Field(default=None, ge=0)
    bid: float | None = Field(default=None, ge=0)
    ask: float | None = Field(default=None, ge=0)
    iv: float | None = Field(default=None, ge=0)
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None

    @model_validator(mode="after")
    def _finish(self) -> "OptionChainEntry":
        self.expiry_date = ensure_ist(self.expiry_date)
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            # Reconcile inverted spread from feed anomaly
            self.ask = self.bid
        return self

    @property
    def is_call(self) -> bool:
        return self.option_type == OptionType.CALL

    @property
    def is_put(self) -> bool:
        return not self.is_call


class OptionChainSnapshot(BaseModel):
    """Full option chain for an underlying + expiry at a point in time."""

    underlying_symbol: str
    timestamp: datetime
    spot_price: float = Field(gt=0)
    expiry_date: datetime
    entries: list[OptionChainEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _finish(self) -> "OptionChainSnapshot":
        self.timestamp = ensure_ist(self.timestamp)
        self.expiry_date = ensure_ist(self.expiry_date)
        if self.expiry_date <= self.timestamp:
            raise ValueError("expiry_date must be after snapshot timestamp")
        return self

    def calls(self) -> list[OptionChainEntry]:
        return [e for e in self.entries if e.is_call]

    def puts(self) -> list[OptionChainEntry]:
        return [e for e in self.entries if e.is_put]

    @property
    def pcr(self) -> float | None:
        """Put/Call ratio from total OI (computed by the options engine in
        Phase 5; this convenience property is provided for completeness)."""
        if not self.entries:
            return None
        total_calls = sum(e.open_interest for e in self.calls())
        total_puts = sum(e.open_interest for e in self.puts())
        if total_calls == 0:
            return None
        return total_puts / total_calls
