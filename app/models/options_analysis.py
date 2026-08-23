"""Options-analysis domain models (computed by the options engine)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import OptionType, PositionBuild
from app.models.time import ensure_ist


class OptionGreeks(BaseModel):
    """Black-Scholes greeks for one option."""

    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None  # daily
    vega: float | None = None   # per 1% vol
    iv: float | None = None     # implied volatility (decimal, e.g. 0.15)


class StrikePositionAnalysis(BaseModel):
    """OI-position direction for one strike (price x OI change classification)."""

    strike: float = Field(gt=0)
    option_type: OptionType
    change_in_oi: float = 0.0
    price_change_pct: float = 0.0
    build: PositionBuild
    description: str = ""


class OISummary(BaseModel):
    """Aggregate open-interest analysis for one chain."""

    total_call_oi: int = 0
    total_put_oi: int = 0
    pcr: float | None = None
    max_call_oi_strike: float | None = None
    max_put_oi_strike: float | None = None
    call_concentration: float | None = None   # max call OI / total call OI
    put_concentration: float | None = None
    call_resistance: float | None = None      # max-OI call strike above spot
    put_support: float | None = None          # max-OI put strike below spot
    change_in_oi_total_calls: int = 0
    change_in_oi_total_puts: int = 0
    avg_iv: float | None = None


class OptionMetrics(BaseModel):
    """Full computed metrics for one option-chain snapshot."""

    underlying_symbol: str
    timestamp: datetime
    expiry_date: datetime
    spot_price: float = Field(gt=0)

    greeks: dict[str, OptionGreeks] = Field(default_factory=dict)  # key: strike+CE/PE
    oi: OISummary = OISummary()

    atm_strike: float | None = None
    near_strikes: list[float] = Field(default_factory=list)
    iv_expansion: bool = False
    iv_contraction: bool = False

    @model_validator(mode="after")
    def _checks(self) -> "OptionMetrics":
        self.timestamp = ensure_ist(self.timestamp)
        self.expiry_date = ensure_ist(self.expiry_date)
        return self