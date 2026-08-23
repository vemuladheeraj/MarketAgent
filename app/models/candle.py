"""Time-series market data containers: candles and quotes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.time import ensure_ist


class MarketCandle(BaseModel):
    """One OHLCV bar.

    ``open/high/low/close`` must satisfy the standard OHLC relationships
    (high >= max(open, close), low <= min(open, close)). Timestamps are always
    timezone-aware.
    """

    symbol: str
    timestamp: datetime
    open_price: float = Field(gt=0)
    high_price: float = Field(gt=0)
    low_price: float = Field(gt=0)
    close_price: float = Field(gt=0)
    volume: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _finish(self) -> "MarketCandle":
        self.timestamp = ensure_ist(self.timestamp)
        if self.high_price < self.low_price:
            raise ValueError(
                "high_price must be >= low_price "
                f"({self.high_price} < {self.low_price})"
            )
        if self.high_price < max(self.open_price, self.close_price):
            raise ValueError(
                "high_price must be >= open and close "
                f"({self.high_price} < {max(self.open_price, self.close_price)})"
            )
        if self.low_price > min(self.open_price, self.close_price):
            raise ValueError(
                "low_price must be <= open and close "
                f"({self.low_price} > {min(self.open_price, self.close_price)})"
            )
        return self


class MarketQuote(BaseModel):
    """A real-time level-1 market quote.

    Bid/ask are optional for products without continuous two-sided quotes
    (e.g. some indices); when given, bid must be <= ask.
    """

    symbol: str
    timestamp: datetime
    bid: float | None = None
    ask: float | None = None
    last_price: float | None = None
    bid_size: int | None = None
    ask_size: int | None = None
    volume: int = 0

    @model_validator(mode="after")
    def _finish(self) -> "MarketQuote":
        self.timestamp = ensure_ist(self.timestamp)
        if self.bid is not None and self.bid <= 0:
            raise ValueError("bid must be positive")
        if self.ask is not None and self.ask <= 0:
            raise ValueError("ask must be positive")
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise ValueError(f"bid ({self.bid}) must be <= ask ({self.ask})")
        return self