"""Deterministic market-regime classifier.

The classifier consumes measured technical/market inputs and returns a rule
based assessment. Gemini can explain this result later, but it is not involved
in deciding the regime.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import MarketRegime
from app.models.snapshots import BreadthSnapshot
from app.models.technical import TechnicalIndicators
from app.models.time import ensure_ist


class RegimeAssessment(BaseModel):
    """Point-in-time deterministic regime label with supporting factors."""

    symbol: str
    timestamp: datetime
    regime: MarketRegime
    confidence: float = Field(ge=0, le=1)
    trend_score: float = 0.0
    volatility_score: float = 0.0
    breadth_score: float = 0.0
    reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _checks(self) -> "RegimeAssessment":
        self.timestamp = ensure_ist(self.timestamp)
        return self


class RegimeClassifier:
    """Initial rule-based regime classifier.

    Rules intentionally favor ``UNCERTAIN`` when inputs are thin or
    contradictory. Thresholds are configurable at construction time so later
    research can tune them without changing the classifier contract.
    """

    def __init__(
        self,
        *,
        strong_adx: float = 30.0,
        trend_adx: float = 20.0,
        high_vix: float = 20.0,
        low_vix: float = 12.0,
        high_hv: float = 28.0,
        low_hv: float = 12.0,
    ) -> None:
        self.strong_adx = strong_adx
        self.trend_adx = trend_adx
        self.high_vix = high_vix
        self.low_vix = low_vix
        self.high_hv = high_hv
        self.low_hv = low_hv

    def classify(
        self,
        technical: TechnicalIndicators,
        *,
        vix: float | None = None,
        breadth: BreadthSnapshot | None = None,
        event_risk: bool = False,
    ) -> RegimeAssessment:
        reasons: list[str] = []
        if event_risk:
            return RegimeAssessment(
                symbol=technical.symbol,
                timestamp=technical.timestamp,
                regime=MarketRegime.EVENT_DRIVEN,
                confidence=0.7,
                reasons=["event_risk=true"],
            )

        vol_regime = self._volatility_regime(technical, vix, reasons)
        if vol_regime is not None:
            return RegimeAssessment(
                symbol=technical.symbol,
                timestamp=technical.timestamp,
                regime=vol_regime,
                confidence=0.75,
                volatility_score=1.0,
                breadth_score=self._breadth_score(breadth),
                reasons=reasons,
            )

        trend_score, trend_reasons = self._trend_score(technical)
        breadth_score = self._breadth_score(breadth)
        reasons.extend(trend_reasons)
        if breadth_score > 0.25:
            reasons.append("breadth_positive")
        elif breadth_score < -0.25:
            reasons.append("breadth_negative")

        adx = technical.adx_14 or 0.0
        combined = trend_score + 0.25 * breadth_score
        if combined >= 1.25 and adx >= self.strong_adx:
            regime = MarketRegime.STRONG_UPTREND
        elif combined >= 0.6 and adx >= self.trend_adx:
            regime = MarketRegime.UPTREND
        elif combined <= -1.25 and adx >= self.strong_adx:
            regime = MarketRegime.STRONG_DOWNTREND
        elif combined <= -0.6 and adx >= self.trend_adx:
            regime = MarketRegime.DOWNTREND
        elif abs(combined) <= 0.5 and (adx < self.trend_adx or technical.adx_14 is None):
            regime = MarketRegime.RANGE
        else:
            regime = MarketRegime.UNCERTAIN

        confidence = min(0.95, 0.45 + abs(combined) * 0.2 + min(adx, 40.0) / 100.0)
        return RegimeAssessment(
            symbol=technical.symbol,
            timestamp=technical.timestamp,
            regime=regime,
            confidence=confidence,
            trend_score=trend_score,
            volatility_score=0.0,
            breadth_score=breadth_score,
            reasons=reasons,
        )

    def _volatility_regime(
        self,
        technical: TechnicalIndicators,
        vix: float | None,
        reasons: list[str],
    ) -> MarketRegime | None:
        hv = technical.historical_volatility_20
        if vix is not None and vix >= self.high_vix:
            reasons.append("vix_high")
            return MarketRegime.HIGH_VOLATILITY
        if hv is not None and hv >= self.high_hv:
            reasons.append("historical_volatility_high")
            return MarketRegime.HIGH_VOLATILITY
        if vix is not None and vix <= self.low_vix:
            reasons.append("vix_low")
            return MarketRegime.LOW_VOLATILITY
        if hv is not None and hv <= self.low_hv:
            reasons.append("historical_volatility_low")
            return MarketRegime.LOW_VOLATILITY
        return None

    @staticmethod
    def _trend_score(technical: TechnicalIndicators) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []
        if technical.sma_20 is not None and technical.sma_50 is not None:
            if technical.sma_20 > technical.sma_50 and technical.close > technical.sma_20:
                score += 1.0
                reasons.append("price_above_rising_averages")
            elif technical.sma_20 < technical.sma_50 and technical.close < technical.sma_20:
                score -= 1.0
                reasons.append("price_below_falling_averages")
        if technical.supertrend_direction is not None:
            score += 0.5 if technical.supertrend_direction > 0 else -0.5
            reasons.append("supertrend_bullish" if technical.supertrend_direction > 0 else "supertrend_bearish")
        if technical.plus_di_14 is not None and technical.minus_di_14 is not None:
            if technical.plus_di_14 > technical.minus_di_14:
                score += 0.4
                reasons.append("plus_di_above_minus_di")
            elif technical.minus_di_14 > technical.plus_di_14:
                score -= 0.4
                reasons.append("minus_di_above_plus_di")
        return score, reasons

    @staticmethod
    def _breadth_score(breadth: BreadthSnapshot | None) -> float:
        if breadth is None or breadth.total <= 0:
            return 0.0
        return (breadth.advancers - breadth.decliners) / breadth.total
