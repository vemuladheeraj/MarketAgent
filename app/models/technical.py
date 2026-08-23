"""Technical indicators model produced by the technical analysis engine."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.time import ensure_ist


class MarketStructure(BaseModel):
    """Price-structure landmarks for the current bar."""

    previous_day_high: float | None = None
    previous_day_low: float | None = None
    weekly_high: float | None = None
    weekly_low: float | None = None
    opening_range_high: float | None = None
    opening_range_low: float | None = None
    support: float | None = None
    resistance: float | None = None
    is_breakout: bool = False
    is_breakdown: bool = False
    gap_pct: float | None = None


class TechnicalIndicators(BaseModel):
    """Computed deterministic indicators for one instrument at one point."""

    symbol: str
    timestamp: datetime
    close: float = Field(gt=0)

    # trend
    sma_20: float | None = None
    sma_50: float | None = None
    ema_9: float | None = None
    ema_12: float | None = None
    ema_26: float | None = None
    vwap: float | None = None
    supertrend_value: float | None = None
    supertrend_direction: float | None = None  # +1 bullish, -1 bearish

    # momentum
    rsi_14: float | None = Field(default=None, ge=0, le=100)
    macd: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    roc_10: float | None = None

    # volatility
    atr_14: float | None = Field(default=None, gt=0)
    historical_volatility_20: float | None = None  # annualised %
    bollinger_lower: float | None = None
    bollinger_mid: float | None = None
    bollinger_upper: float | None = None

    # trend strength
    adx_14: float | None = Field(default=None, ge=0, le=100)
    plus_di_14: float | None = None
    minus_di_14: float | None = None

    # volume
    relative_volume: float | None = None
    volume_spike: bool = False
    volume_confirmation: bool = False

    # structure
    structure: MarketStructure = MarketStructure()

    @model_validator(mode="after")
    def _checks(self) -> "TechnicalIndicators":
        self.timestamp = ensure_ist(self.timestamp)
        return self