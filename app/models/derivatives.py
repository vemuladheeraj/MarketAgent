"""Derivatives and flow-of-funds domain models used by the market-data layer."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.candle import MarketQuote
from app.models.instruments import FutureContract
from app.models.time import ensure_ist


class FuturesSnapshot(BaseModel):
    """Point-in-time quote for one futures contract."""

    contract: FutureContract
    quote: MarketQuote

    @model_validator(mode="after")
    def _chk(self) -> "FuturesSnapshot":
        self.contract.expiry_date = ensure_ist(self.contract.expiry_date)
        self.quote.timestamp = ensure_ist(self.quote.timestamp)
        return self


class FIIDIIFlow(BaseModel):
    """FII / DII net flow snapshot (values in INR crores unless noted)."""

    timestamp: datetime
    fii_cash_net: float | None = Field(
        default=None, description="FII net buy in the cash segment (INR crores)"
    )
    dii_cash_net: float | None = Field(
        default=None, description="DII net buy in the cash segment (INR crores)"
    )
    fii_index_futures_net: float | None = Field(
        default=None, description="FII net notional in index futures (INR crores)"
    )
    fii_index_options_net: float | None = Field(
        default=None, description="FII net premium in index options (INR crores)"
    )

    @model_validator(mode="after")
    def _checks(self) -> "FIIDIIFlow":
        self.timestamp = ensure_ist(self.timestamp)
        return self