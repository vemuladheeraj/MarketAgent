"""Tests for deterministic market-regime classification."""

from __future__ import annotations

from datetime import datetime

from app.analysis.regime import RegimeClassifier
from app.models import BreadthSnapshot, MarketRegime, TechnicalIndicators
from app.models.time import IST


def _tech(**overrides) -> TechnicalIndicators:
    base = dict(
        symbol="NIFTY",
        timestamp=datetime(2025, 6, 27, 15, 29, tzinfo=IST),
        close=110,
        sma_20=105,
        sma_50=100,
        supertrend_direction=1,
        adx_14=32,
        plus_di_14=30,
        minus_di_14=12,
        historical_volatility_20=16,
    )
    base.update(overrides)
    return TechnicalIndicators(**base)


def test_strong_uptrend():
    assessment = RegimeClassifier().classify(
        _tech(),
        breadth=BreadthSnapshot(
            timestamp=datetime(2025, 6, 27, 15, 29, tzinfo=IST),
            advancers=1200,
            decliners=500,
            unchanged=100,
        ),
    )
    assert assessment.regime == MarketRegime.STRONG_UPTREND
    assert assessment.confidence > 0.5


def test_downtrend():
    assessment = RegimeClassifier().classify(
        _tech(
            close=90,
            sma_20=95,
            sma_50=100,
            supertrend_direction=-1,
            plus_di_14=10,
            minus_di_14=30,
        )
    )
    assert assessment.regime == MarketRegime.STRONG_DOWNTREND


def test_high_volatility_overrides_trend():
    assessment = RegimeClassifier().classify(_tech(), vix=24)
    assert assessment.regime == MarketRegime.HIGH_VOLATILITY


def test_event_risk_overrides():
    assessment = RegimeClassifier().classify(_tech(), event_risk=True)
    assert assessment.regime == MarketRegime.EVENT_DRIVEN


def test_range_when_adx_is_weak_and_trend_is_flat():
    assessment = RegimeClassifier().classify(
        _tech(
            close=100,
            sma_20=100,
            sma_50=100,
            supertrend_direction=None,
            adx_14=12,
            plus_di_14=18,
            minus_di_14=18,
            historical_volatility_20=16,
        )
    )
    assert assessment.regime == MarketRegime.RANGE


def test_uncertain_when_trend_signals_conflict():
    assessment = RegimeClassifier().classify(
        _tech(
            close=110,
            sma_20=105,
            sma_50=100,
            supertrend_direction=-1,
            adx_14=25,
            plus_di_14=10,
            minus_di_14=30,
            historical_volatility_20=16,
        )
    )
    assert assessment.regime == MarketRegime.UNCERTAIN


def test_low_volatility_overrides_trend():
    assessment = RegimeClassifier().classify(_tech(), vix=11)
    assert assessment.regime == MarketRegime.LOW_VOLATILITY


def test_classifier_module_does_not_import_gemini():
    import ast
    from pathlib import Path

    import app.analysis.regime.classifier as module

    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    assert not any(name.startswith("app.ai") or "gemini" in name.lower() for name in imported)
