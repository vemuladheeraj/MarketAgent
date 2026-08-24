"""Strategy framework tests. Candidates are research objects, not trade advice."""

from __future__ import annotations

from datetime import datetime

from app.analysis.regime import RegimeAssessment
from app.models import (
    DataQuality,
    Direction,
    MarketRegime,
    MarketStructure,
    OISummary,
    OptionMetrics,
    TechnicalIndicators,
)
from app.models.time import IST
from app.strategies import StrategyContext, StrategyEngine, default_strategies
from app.strategies.implementations import (
    BearPutSpreadStrategy,
    BreakoutVolumeConfirmationStrategy,
    BullCallSpreadStrategy,
    MeanReversionStrategy,
    OIPriceConfirmationStrategy,
    OpeningRangeBreakoutStrategy,
    SupportResistanceReversalStrategy,
    TrendContinuationStrategy,
    VWAPMomentumStrategy,
)


TS = datetime(2025, 6, 27, 15, 29, tzinfo=IST)


def _tech(**overrides) -> TechnicalIndicators:
    base = dict(
        symbol="NIFTY",
        timestamp=TS,
        close=110,
        sma_20=105,
        sma_50=100,
        vwap=108,
        rsi_14=58,
        atr_14=2.0,
        adx_14=32,
        volume_confirmation=True,
        structure=MarketStructure(
            opening_range_high=108,
            opening_range_low=100,
            support=109.5,
            resistance=120,
            is_breakout=True,
        ),
        bollinger_lower=111,
        bollinger_mid=115,
    )
    base.update(overrides)
    return TechnicalIndicators(**base)


def _regime(label: MarketRegime) -> RegimeAssessment:
    return RegimeAssessment(
        symbol="NIFTY",
        timestamp=TS,
        regime=label,
        confidence=0.7,
    )


def _options(pcr: float = 1.2) -> OptionMetrics:
    return OptionMetrics(
        underlying_symbol="NIFTY",
        timestamp=TS,
        expiry_date=datetime(2025, 7, 31, tzinfo=IST),
        spot_price=110,
        oi=OISummary(pcr=pcr, total_call_oi=1000, total_put_oi=1200),
    )


def _context(regime: MarketRegime, **tech) -> StrategyContext:
    return StrategyContext(
        technical=_tech(**tech),
        regime=_regime(regime),
        options=_options(),
        breadth_score=0.4,
    )


def test_default_strategy_set_has_nine_named_strategies():
    names = [s.name for s in default_strategies()]
    assert names == [
        "opening_range_breakout",
        "vwap_momentum",
        "trend_continuation",
        "support_resistance_reversal",
        "oi_price_confirmation",
        "breakout_volume_confirmation",
        "mean_reversion",
        "bull_call_spread",
        "bear_put_spread",
    ]


def test_opening_range_breakout_requires_uptrend_and_break():
    orb = OpeningRangeBreakoutStrategy()
    bull = _context(MarketRegime.STRONG_UPTREND)
    assert orb.is_applicable(bull)
    candidate = orb.generate_candidate(bull)
    assert candidate is not None
    assert candidate.direction == Direction.LONG
    assert candidate.entry == 110
    assert candidate.stop_loss == 100
    assert candidate.targets[0] == 130
    assert candidate.risk_reward == 2.0
    assert candidate.probability_is_calibrated is False
    assert orb.calculate_entry(bull) == 110
    assert orb.calculate_stop_loss(bull) == 100

    ranged = _context(MarketRegime.RANGE)
    assert not orb.is_applicable(ranged)
    assert orb.generate_candidate(ranged) is None

    no_break = _context(MarketRegime.UPTREND, close=107)
    assert orb.generate_candidate(no_break) is None


def test_vwap_momentum_and_trend_continuation_in_uptrend():
    ctx = _context(MarketRegime.UPTREND)
    vwap = VWAPMomentumStrategy().generate_candidate(ctx)
    trend = TrendContinuationStrategy().generate_candidate(ctx)
    assert vwap is not None and vwap.entry > vwap.stop_loss
    assert trend is not None and trend.stop_loss <= ctx.technical.sma_20


def test_support_resistance_and_mean_reversion_prefer_range():
    sr = SupportResistanceReversalStrategy()
    mr = MeanReversionStrategy()
    up = _context(MarketRegime.UPTREND)
    assert sr.generate_candidate(up) is None
    assert mr.generate_candidate(up) is None

    rng = _context(
        MarketRegime.RANGE,
        close=100,
        sma_20=100,
        rsi_14=32,
        structure=MarketStructure(support=100, resistance=110),
        bollinger_lower=100.5,
        bollinger_mid=108,
    )
    sr_c = sr.generate_candidate(rng)
    assert sr_c is not None
    assert sr_c.targets[0] == 110

    mr_ctx = _context(
        MarketRegime.RANGE,
        close=99,
        rsi_14=30,
        bollinger_lower=100,
        bollinger_mid=108,
    )
    mr_c = mr.generate_candidate(mr_ctx)
    assert mr_c is not None
    assert mr_c.targets[0] == 108


def test_oi_confirmation_requires_pcr_and_options():
    strat = OIPriceConfirmationStrategy()
    ctx = _context(MarketRegime.UPTREND)
    assert strat.generate_candidate(ctx) is not None

    no_opt = StrategyContext(
        technical=_tech(),
        regime=_regime(MarketRegime.UPTREND),
        options=None,
    )
    assert strat.generate_candidate(no_opt) is None

    weak_pcr = _context(MarketRegime.UPTREND)
    weak_pcr = weak_pcr.model_copy(
        update={"options": _options(pcr=0.6)}
    )
    assert strat.generate_candidate(weak_pcr) is None


def test_breakout_volume_and_spreads():
    ctx = _context(MarketRegime.STRONG_UPTREND)
    assert BreakoutVolumeConfirmationStrategy().generate_candidate(ctx) is not None
    assert BullCallSpreadStrategy().generate_candidate(ctx) is not None

    down = _context(
        MarketRegime.DOWNTREND,
        close=90,
        sma_20=95,
        atr_14=2,
    )
    bear = BearPutSpreadStrategy().generate_candidate(down)
    assert bear is not None
    assert bear.direction == Direction.SHORT
    assert bear.stop_loss > bear.entry
    assert BearPutSpreadStrategy().calculate_expected_value(3.0, 2.0, 0.5) == 0.5


def test_engine_skips_invalid_data_and_non_applicable_strategies(fresh_settings):
    engine = StrategyEngine(
        signal_config=fresh_settings.signal,
        strategy_config=fresh_settings.strategies,
    )
    ctx = _context(MarketRegime.STRONG_UPTREND)
    assert engine.evaluate(ctx, data_quality=DataQuality.INVALID) == []

    signals = engine.evaluate(ctx, data_quality=DataQuality.VALID)
    names = {s.candidate.strategy_name for s in signals}
    assert "opening_range_breakout" in names
    assert "mean_reversion" not in names
    assert "support_resistance_reversal" not in names


def test_engine_respects_enabled_flags(fresh_settings):
    settings = fresh_settings.model_copy(deep=True)
    settings.strategies.enabled = {"opening_range_breakout": True}
    engine = StrategyEngine(
        signal_config=settings.signal,
        strategy_config=settings.strategies,
    )
    signals = engine.evaluate(_context(MarketRegime.STRONG_UPTREND))
    assert [s.candidate.strategy_name for s in signals] == ["opening_range_breakout"]
