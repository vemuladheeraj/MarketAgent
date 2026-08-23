"""Composite snapshot models combining quotes, options, and market context."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.candle import MarketQuote
from app.models.options import OptionChainSnapshot
from app.models.time import ensure_ist


class BreadthSnapshot(BaseModel):
    """Market breadth snapshot (advancers/decliners/unchanged)."""

    timestamp: datetime
    advancers: int = Field(default=0, ge=0)
    decliners: int = Field(default=0, ge=0)
    unchanged: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _finish(self) -> "BreadthSnapshot":
        self.timestamp = ensure_ist(self.timestamp)
        return self

    @property
    def total(self) -> int:
        return self.advancers + self.decliners + self.unchanged

    @property
    def advance_decline_ratio(self) -> float | None:
        if self.decliners == 0:
            return None if self.advancers == 0 else float("inf")
        return self.advancers / self.decliners


class MarketSnapshot(BaseModel):
    """Point-in-time aggregation of the whole watched market.

    Optional fields (VIX, FII/DII, breadth, options chains, regime) are filled
    by the collection/analysis pipeline; ``None`` means *not available yet*,
    never a fabricated value.
    """

    timestamp: datetime
    quotes: dict[str, MarketQuote] = Field(default_factory=dict)
    vix: float | None = None
    fii_net_buy: float | None = None
    dii_net_buy: float | None = None
    breadth: BreadthSnapshot | None = None
    option_chains: dict[str, OptionChainSnapshot] = Field(default_factory=dict)
    regime: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _finish(self) -> "MarketSnapshot":
        self.timestamp = ensure_ist(self.timestamp)
        if self.vix is not None and self.vix < 0:
            raise ValueError("vix cannot be negative")
        return self