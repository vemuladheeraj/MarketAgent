"""Deterministic signal scoring.

Weights and bands are research configuration, not evidence of profitability.
INVALID market data always yields a rejected NO_TRADE result.
"""

from __future__ import annotations

from app.config.settings import SignalConfig
from app.models.enums import DataQuality, SignalClassification
from app.models.trading import Signal, StrategyCandidate


class SignalScorer:
    """Weighted scoring over candidate factor strengths in [0, 1]."""

    def __init__(self, config: SignalConfig) -> None:
        self.config = config

    def score(
        self,
        candidate: StrategyCandidate,
        *,
        data_quality: DataQuality = DataQuality.VALID,
        extra_factors: dict[str, float] | None = None,
    ) -> Signal:
        reasons: list[str] = []
        factors = dict(candidate.factors)
        factors.setdefault("risk_reward", self._risk_reward_strength(candidate.risk_reward))
        if extra_factors:
            for name, value in extra_factors.items():
                factors.setdefault(name, value)

        raw = 0.0
        for factor, weight in self.config.weights.items():
            strength = max(0.0, min(1.0, factors.get(factor, 0.0)))
            raw += weight * strength
        raw = round(raw, 4)
        classification = self.classify(raw)

        if data_quality == DataQuality.INVALID:
            reasons.append("data_quality_invalid")
        if candidate.risk_reward < self.config.min_risk_reward:
            reasons.append("risk_reward_below_minimum")
        if raw < self.config.min_signal_score:
            reasons.append("score_below_minimum")
        if classification == SignalClassification.NO_TRADE:
            reasons.append("classification_no_trade")

        accepted = not reasons and data_quality != DataQuality.INVALID
        if data_quality == DataQuality.INVALID:
            classification = SignalClassification.NO_TRADE
            accepted = False

        return Signal(
            candidate=candidate,
            score=raw,
            classification=classification,
            accepted=accepted,
            rejection_reasons=reasons,
            data_quality=data_quality,
            timestamp=candidate.timestamp,
        )

    def classify(self, score: float) -> SignalClassification:
        bands = self.config.bands
        if score >= bands.exceptional:
            return SignalClassification.EXCEPTIONAL
        if score >= bands.high_quality:
            return SignalClassification.HIGH_QUALITY
        if score >= bands.valid:
            return SignalClassification.VALID
        if score >= bands.watch:
            return SignalClassification.WATCH
        if score >= bands.weak:
            return SignalClassification.WEAK
        return SignalClassification.NO_TRADE

    def _risk_reward_strength(self, risk_reward: float) -> float:
        minimum = self.config.min_risk_reward
        if risk_reward <= 0 or minimum <= 0:
            return 0.0
        return max(0.0, min(1.0, risk_reward / (2.0 * minimum)))
