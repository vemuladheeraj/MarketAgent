"""Deterministic signal-scoring tests."""

from __future__ import annotations

from datetime import datetime

from app.config.settings import SignalConfig
from app.models import DataQuality, Direction, SignalClassification, StrategyCandidate
from app.models.time import IST
from app.scoring import SignalScorer


def _candidate(**overrides) -> StrategyCandidate:
    base = dict(
        strategy_name="trend_continuation",
        symbol="NIFTY",
        timestamp=datetime(2025, 6, 27, 15, 29, tzinfo=IST),
        direction=Direction.LONG,
        entry=100,
        stop_loss=98,
        targets=[104],
        expected_win=4,
        expected_loss=2,
        expected_value=1,
        probability=0.5,
        factors={
            "trend": 1.0,
            "momentum": 1.0,
            "price_structure": 1.0,
            "volume": 1.0,
            "oi": 1.0,
            "options_structure": 1.0,
            "volatility": 1.0,
            "breadth": 1.0,
            "risk_reward": 1.0,
        },
    )
    base.update(overrides)
    return StrategyCandidate(**base)


def test_full_strength_is_exceptional_and_accepted():
    scorer = SignalScorer(SignalConfig())
    signal = scorer.score(_candidate())
    assert signal.score == 100
    assert signal.classification == SignalClassification.EXCEPTIONAL
    assert signal.accepted is True
    assert signal.rejection_reasons == []


def test_zero_factors_is_no_trade():
    scorer = SignalScorer(SignalConfig())
    signal = scorer.score(_candidate(factors={}))
    # risk_reward is derived from the 2.0 R:R vs min 1.5 -> 2/3 strength * weight 5
    assert signal.classification in {
        SignalClassification.NO_TRADE,
        SignalClassification.WEAK,
    }
    assert signal.accepted is False
    assert "score_below_minimum" in signal.rejection_reasons


def test_score_bands():
    scorer = SignalScorer(SignalConfig())
    assert scorer.classify(90) == SignalClassification.EXCEPTIONAL
    assert scorer.classify(80) == SignalClassification.HIGH_QUALITY
    assert scorer.classify(70) == SignalClassification.VALID
    assert scorer.classify(60) == SignalClassification.WATCH
    assert scorer.classify(50) == SignalClassification.WEAK
    assert scorer.classify(49.9) == SignalClassification.NO_TRADE


def test_invalid_data_cannot_be_accepted():
    scorer = SignalScorer(SignalConfig())
    signal = scorer.score(_candidate(), data_quality=DataQuality.INVALID)
    assert signal.accepted is False
    assert signal.classification == SignalClassification.NO_TRADE
    assert "data_quality_invalid" in signal.rejection_reasons


def test_poor_risk_reward_is_rejected_even_if_score_is_high():
    scorer = SignalScorer(SignalConfig())
    signal = scorer.score(
        _candidate(stop_loss=90, targets=[101], expected_win=1, expected_loss=10)
    )
    assert signal.candidate.risk_reward < 1.5
    assert signal.accepted is False
    assert "risk_reward_below_minimum" in signal.rejection_reasons


def test_warning_data_does_not_force_no_trade():
    scorer = SignalScorer(SignalConfig())
    signal = scorer.score(_candidate(), data_quality=DataQuality.WARNING)
    assert signal.classification == SignalClassification.EXCEPTIONAL
    assert signal.accepted is True
    assert signal.data_quality == DataQuality.WARNING
