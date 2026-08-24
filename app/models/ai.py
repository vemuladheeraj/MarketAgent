"""Domain models for AI and Gemini contextual reasoning."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field, model_validator

from app.models.time import ensure_ist, now_ist


class NewsItem(BaseModel):
    """Headline or macro announcement contextual item."""

    news_id: str = Field(default_factory=lambda: f"news_{uuid.uuid4().hex[:8]}")
    timestamp: datetime
    headline: str
    source: str = "general"
    category: str = "market"  # rbi, fed, inflation, crude, earnings, etc.
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    symbols: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _checks(self) -> "NewsItem":
        self.timestamp = ensure_ist(self.timestamp)
        return self


class Contradiction(BaseModel):
    """Conflict identified between quantitative factors."""

    factor_a: str
    factor_b: str
    description: str
    severity: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"


class GeminiAnalysis(BaseModel):
    """Structured reasoning output from Gemini contextual interpretation."""

    analysis_id: str = Field(default_factory=lambda: f"ai_{uuid.uuid4().hex[:8]}")
    timestamp: datetime = Field(default_factory=now_ist)
    symbol: str
    summary: str
    market_bias: Literal["BULLISH", "BEARISH", "NEUTRAL", "UNCERTAIN"]
    key_factors: list[str] = Field(default_factory=list)
    supporting_factors: list[str] = Field(default_factory=list)
    conflicting_factors: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    signal_interpretation: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str
    contradictions: list[Contradiction] = Field(default_factory=list)
    grounded_data_summary: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _checks(self) -> "GeminiAnalysis":
        self.timestamp = ensure_ist(self.timestamp)
        return self
