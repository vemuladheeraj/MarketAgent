"""Market instrument domain models.

These are the strongly-typed identifiers the whole platform consumes and
produces. Prices are represented with ``float`` for seamless interop with
pandas/NumPy; lot/contract sizes are integers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import InstrumentKind, OptionType
from app.models.time import ensure_ist


class Instrument(BaseModel):
    """Base market instrument."""

    symbol: str
    name: str = ""
    kind: InstrumentKind

    @field_validator("symbol")
    @classmethod
    def _symbol_not_blank(cls, value: str) -> str:
        symbol = value.strip()
        if not symbol:
            raise ValueError("symbol cannot be blank")
        return symbol.upper()

    def __str__(self) -> str:  # pragma: no cover - trivial
        suffix = f" {self.expiry_date:%Y-%m-%d}" if hasattr(self, "expiry_date") else ""
        return f"{self.symbol}{suffix}"


class FutureContract(Instrument):
    """Futures contract on an underlying (index or equity)."""

    kind: Literal[InstrumentKind.FUTURE] = InstrumentKind.FUTURE
    underlying_symbol: str
    expiry_date: datetime
    contract_size: int = Field(gt=0, description="Units per contract.")
    lot_size: int = Field(gt=0, description="Tradable lot multiple.")
    tick_size: float = Field(default=0.05, gt=0)

    @model_validator(mode="after")
    def _validate(self) -> "FutureContract":
        self.expiry_date = ensure_ist(self.expiry_date)
        if not self.underlying_symbol.strip():
            raise ValueError("underlying_symbol cannot be blank")
        return self


class OptionContract(Instrument):
    """Index/equity option contract on a given strike and expiry."""

    kind: Literal[InstrumentKind.OPTION] = InstrumentKind.OPTION
    underlying_symbol: str
    expiry_date: datetime
    strike: float = Field(gt=0)
    option_type: OptionType
    lot_size: int = Field(default=75, gt=0)
    instrument_token: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> "OptionContract":
        self.expiry_date = ensure_ist(self.expiry_date)
        if not self.underlying_symbol.strip():
            raise ValueError("underlying_symbol cannot be blank")
        if self.strike <= 0:
            raise ValueError("strike must be positive")
        return self

    @property
    def option_key(self) -> str:
        """Composite key e.g. NIFTY 24500 CE 27-JUN-2024."""
        side = "CE" if self.option_type == OptionType.CALL else "PE"
        return (
            f"{self.underlying_symbol} {self.strike:g} {side} "
            f"{self.expiry_date:%d-%b-%Y}".upper()
        )

    @property
    def is_call(self) -> bool:
        return self.option_type == OptionType.CALL

    @property
    def is_put(self) -> bool:
        return not self.is_call