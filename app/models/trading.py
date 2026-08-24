"""Strategy-candidate and signal models.

These are quantitative-layer outputs. A high score is not evidence of
profitability; it is only a deterministic classification of the supplied
factors. Probability fields default to an uninformed prior (0.5) unless a
later calibration phase replaces them with historically estimated values.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import DataQuality, Direction, SignalClassification
from app.models.time import ensure_ist


class StrategyCandidate(BaseModel):
    """A deterministic setup candidate emitted by a strategy."""

    strategy_name: str
    symbol: str
    timestamp: datetime
    direction: Direction
    entry: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    targets: list[float] = Field(default_factory=list)
    invalidation: str = ""
    expected_win: float = 0.0
    expected_loss: float = 0.0
    expected_value: float = 0.0
    probability: float = Field(default=0.5, ge=0, le=1)
    probability_is_calibrated: bool = False
    factors: dict[str, float] = Field(default_factory=dict)
    explanation: str = ""

    @model_validator(mode="after")
    def _checks(self) -> "StrategyCandidate":
        self.timestamp = ensure_ist(self.timestamp)
        if not self.targets:
            raise ValueError("candidate must include at least one target")
        if self.direction == Direction.LONG and self.stop_loss >= self.entry:
            raise ValueError("long stop_loss must be below entry")
        if self.direction == Direction.SHORT and self.stop_loss <= self.entry:
            raise ValueError("short stop_loss must be above entry")
        return self

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.stop_loss)

    @property
    def first_target_reward(self) -> float:
        return abs(self.targets[0] - self.entry)

    @property
    def risk_reward(self) -> float:
        return 0.0 if self.risk_per_unit <= 0 else self.first_target_reward / self.risk_per_unit


class Signal(BaseModel):
    """Scored setup candidate. ``accepted`` is a research gate, not a trade."""

    candidate: StrategyCandidate
    score: float = Field(ge=0, le=100)
    classification: SignalClassification
    accepted: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    data_quality: DataQuality = DataQuality.VALID
    timestamp: datetime

    @model_validator(mode="after")
    def _checks(self) -> "Signal":
        self.timestamp = ensure_ist(self.timestamp)
        return self
