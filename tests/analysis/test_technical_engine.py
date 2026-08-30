"""Tests for the TechnicalAnalyzer and market-structure helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.analysis.technical.engine import TechnicalAnalyzer
from app.analysis.technical.market_structure import (
    breakout_breakdown,
    compute_structure,
    gap_pct,
    opening_range,
    previous_day_high_low,
    support_resistance,
    weekly_high_low,
)
from app.data.normalizers import MarketDataNormalizer
from app.models.candle import MarketCandle
from app.models.time import IST
from tests.fixtures.provider_payloads import sample_candles

NORMALIZER = MarketDataNormalizer()
ANALYZER = TechnicalAnalyzer()


def _ts(i: int) -> datetime:
    return datetime(2025, 6, 1, tzinfo=IST) + timedelta(days=i)


def _mk(closes, highs, lows, volumes=None):
    volumes = volumes or [1000] * len(closes)
    return [
        MarketCandle(
            symbol="NIFTY", timestamp=_ts(i),
            open_price=closes[i], high_price=highs[i],
            low_price=lows[i], close_price=closes[i],
            volume=volumes[i],
        )
        for i in range(len(closes))
    ]


class TestMarketStructure:
    def test_previous_day_high_low(self):
        candles = _mk([100, 101, 102], [102, 103, 104], [98, 99, 100])
        hi, lo = previous_day_high_low(candles)
        assert (hi, lo) == (103.0, 99.0)  # second-to-last bar

    def test_weekly_high_low(self):
        # Mon 2025-06-02 .. Sun 2025-06-08 all in one ISO week
        week_candles = [
            MarketCandle(
                symbol="NIFTY",
                timestamp=datetime(2025, 6, d, tzinfo=IST),
                open_price=100.0, high_price=102.0,
                low_price=98.0, close_price=100.0, volume=1000,
            )
            for d in range(2, 9)
        ]
        hi, lo = weekly_high_low(week_candles)
        assert (hi, lo) == (102.0, 98.0)

    def test_breakout_breakdown(self):
        closes = [100, 101, 102, 103, 104]
        highs = [101, 102, 103, 104, 105]
        lows = [99, 100, 101, 102, 103]
        candles = _mk(closes, highs, lows)
        bo, bd = breakout_breakdown(candles, lookback=3)
        assert (bo, bd) == (False, False)
        # current close 105 > prior max high 104 -> breakout
        candles2 = _mk([100, 101, 102, 103, 105],
                       [101, 102, 103, 104, 106],
                       [99, 100, 101, 102, 103])
        bo2, bd2 = breakout_breakdown(candles2, lookback=3)
        assert (bo2, bd2) == (True, False)
        # current close 105 < prior min low 106 -> breakdown
        down = _mk([110, 109, 108, 107, 104],
                   [112, 111, 110, 109, 106],
                   [108, 107, 106, 105, 104])
        bo3, bd3 = breakout_breakdown(down, lookback=3)
        assert (bo3, bd3) == (False, True)

    def test_gap_pct(self):
        # open of last bar defaults to its close (105); prev close = 100 -> +5%
        closes = [100, 105]
        highs = [102, 112]
        lows = [98, 104]
        candles = _mk(closes, highs, lows, volumes=[1000, 2000])
        assert gap_pct(candles) == pytest.approx(5.0)

    def test_support_resistance(self):
        closes = [100, 102, 101, 103, 104, 103, 105, 106, 107, 106, 108]
        highs = [c + 1 for c in closes]
        lows = [c - 1 for c in closes]
        candles = _mk(closes, highs, lows)
        support, resistance = support_resistance(candles, lookback=10)
        assert support is not None and support <= candles[-1].close_price
        assert resistance is None or resistance >= candles[-1].close_price

    def test_compute_structure_end_to_end(self):
        closes = [100, 102, 105, 103, 108, 107, 110, 112]
        candles = _mk(closes, [c + 2 for c in closes], [c - 2 for c in closes])
        structure = compute_structure(candles)
        assert structure.previous_day_high is not None
        assert structure.is_breakout in (True, False)


class TestTechnicalAnalyzer:
    def _candles(self, n: int = 80) -> list[MarketCandle]:
        raw = sample_candles("NIFTY", n)
        return NORMALIZER.normalize_candle_list(raw)

    def test_analyze_produces_model(self):
        indicators = ANALYZER.analyze(self._candles())
        assert indicators.symbol == "NIFTY"
        assert indicators.timestamp.tzinfo is not None
        assert indicators.rsi_14 is not None
        assert indicators.atr_14 is not None
        assert indicators.sma_20 is not None

    def test_analyze_deterministic(self):
        a = ANALYZER.analyze(self._candles())
        b = ANALYZER.analyze(self._candles())
        assert a.model_dump() == b.model_dump()

    def test_analyze_too_few_candles_raises(self):
        with pytest.raises(ValueError):
            ANALYZER.analyze([])

    def test_analyze_short_series_partial_when_values_missing(self):
        candles = self._candles(30)  # < 50 -> some indicators None
        indicators = ANALYZER.analyze(candles)
        assert indicators.rsi_14 is not None
        assert indicators.sma_50 is None


def down_candles():
    return None