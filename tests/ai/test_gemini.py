"""Unit tests for Gemini AI contextual layer and contradiction detection."""

from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from app.ai.contradictions import ContradictionDetector
from app.ai.gemini.client import GeminiClient
from app.ai.news import NewsContextManager
from app.analysis.regime.classifier import RegimeAssessment
from app.config.settings import GeminiConfig
from app.models.ai import NewsItem
from app.models.enums import MarketRegime
from app.models.options_analysis import OISummary, OptionMetrics
from app.models.snapshots import BreadthSnapshot
from app.models.technical import MarketStructure, TechnicalIndicators
from app.models.time import IST

TS = datetime(2025, 6, 27, 15, 30, tzinfo=IST)


def _indicators(
    *,
    close: float = 20000.0,
    sma20: float = 19900.0,
    supertrend_dir: int = 1,
    is_breakout: bool = False,
    vol_conf: bool = True,
    adx: float = 25.0,
) -> TechnicalIndicators:
    return TechnicalIndicators(
        symbol="NIFTY",
        timestamp=TS,
        close=close,
        sma_20=sma20,
        supertrend_direction=supertrend_dir,
        adx_14=adx,
        volume_confirmation=vol_conf,
        structure=MarketStructure(
            support=19800.0,
            resistance=20200.0,
            is_breakout=is_breakout,
        ),
    )


def _regime(reg: MarketRegime = MarketRegime.UPTREND, confidence: float = 0.8) -> RegimeAssessment:
    return RegimeAssessment(
        symbol="NIFTY",
        timestamp=TS,
        regime=reg,
        confidence=confidence,
        trend_score=1.0,
    )


class TestContradictionDetector:
    def test_call_resistance_contradiction(self):
        detector = ContradictionDetector()
        tech = _indicators(close=20000.0, sma20=19900.0)
        options = OptionMetrics(
            timestamp=TS,
            expiry_date=TS + timedelta(days=7),
            spot_price=20000.0,
            underlying_symbol="NIFTY",
            oi=OISummary(
                total_call_oi=100000,
                total_put_oi=80000,
                call_resistance=20000.0,  # right at resistance
                pcr=0.8,
            ),
        )
        contradictions = detector.analyze(
            technical=tech,
            regime=_regime(),
            options=options,
        )
        assert any("Call Resistance" in c.factor_b for c in contradictions)

    def test_unconfirmed_breakout_contradiction(self):
        detector = ContradictionDetector()
        tech = _indicators(close=20050.0, is_breakout=True, vol_conf=False)
        contradictions = detector.analyze(
            technical=tech,
            regime=_regime(),
        )
        assert any("Volume Confirmation Missing" in c.factor_b for c in contradictions)

    def test_breadth_divergence_contradiction(self):
        detector = ContradictionDetector()
        tech = _indicators(close=20000.0, sma20=19900.0)
        breadth = BreadthSnapshot(timestamp=TS, advancers=200, decliners=800, unchanged=0)
        contradictions = detector.analyze(
            technical=tech,
            regime=_regime(),
            breadth=breadth,
        )
        assert any("Negative Market Breadth" in c.factor_b for c in contradictions)


class TestGeminiClient:
    def test_deterministic_synthesis_structure(self):
        config = GeminiConfig(api_key="")  # offline mode
        client = GeminiClient(config)
        tech = _indicators(close=20000.0, sma20=19900.0, is_breakout=True, vol_conf=False)
        reg = _regime(MarketRegime.UPTREND, confidence=0.85)

        analysis = client.analyze_market(
            technical=tech,
            regime=reg,
        )
        assert analysis.symbol == "NIFTY"
        assert analysis.market_bias == "BULLISH"
        assert len(analysis.key_factors) >= 2
        assert len(analysis.contradictions) >= 1
        assert "Unconfirmed breakout" in " ".join(analysis.risks)
        assert analysis.confidence == 0.85
        assert analysis.grounded_data_summary["close"] == 20000.0


class TestNewsContextManager:
    def test_news_aggregation_and_sentiment(self):
        mgr = NewsContextManager()
        mgr.add_news(
            NewsItem(
                timestamp=TS,
                headline="RBI holds repo rate steady",
                category="rbi",
                sentiment_score=0.4,
                symbols=["NIFTY", "BANKNIFTY"],
            )
        )
        mgr.add_news(
            NewsItem(
                timestamp=TS,
                headline="Crude oil spikes on supply concerns",
                category="crude",
                sentiment_score=-0.6,
                symbols=["NIFTY"],
            )
        )

        nifty_news = mgr.get_recent_news("NIFTY")
        assert len(nifty_news) == 2
        sentiment = mgr.aggregate_sentiment("NIFTY")
        # (0.4 + (-0.6)) / 2 = -0.1
        assert abs(sentiment - (-0.1)) < 1e-6
