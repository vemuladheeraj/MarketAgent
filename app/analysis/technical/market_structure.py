"""Price-structure analysis: levels, ranges, breakouts and gaps.

All functions are deterministic and only use information available up to and
including the current bar (no look-ahead).
"""

from __future__ import annotations

from app.models.candle import MarketCandle
from app.models.technical import MarketStructure


def previous_day_high_low(
    candles: list[MarketCandle],
) -> tuple[float | None, float | None]:
    """Return (prev_day_high, prev_day_low) from the last completed day.

    With daily bars the second-to-last bar is the previous session.
    Uses only completed bars (excludes the current forming bar when the
    series ends mid-session — approximated by dropping the last bar only when
    requested externally).
    """
    if len(candles) < 2:
        return None, None
    prev = candles[-2]
    return prev.high_price, prev.low_price


def weekly_high_low(candles: list[MarketCandle]) -> tuple[float | None, float | None]:
    """(high, low) of the current ISO week up to and including the last bar."""
    if not candles:
        return None, None
    last = candles[-1].timestamp
    iso_year, iso_week, _ = last.isocalendar()
    week_bars = [
        c
        for c in candles
        if c.timestamp.isocalendar()[:2] == (iso_year, iso_week)
    ]
    if not week_bars:
        return None, None
    return max(c.high_price for c in week_bars), min(c.low_price for c in week_bars)


def opening_range(
    candles: list[MarketCandle], bars: int = 1
) -> tuple[float | None, float | None]:
    """(high, low) of the first `bars` bars (session opening range)."""
    if not candles:
        return None, None
    first_bars = candles[:bars]
    return max(c.high_price for c in first_bars), min(c.low_price for c in first_bars)


def support_resistance(
    candles: list[MarketCandle], lookback: int = 20
) -> tuple[float | None, float | None]:
    """Simple swing S/R: nearest local low (support) and local high
    (resistance) from pivots in the trailing window (excluding the current
    bar to avoid look-ahead at the decision point)."""
    if len(candles) < 3:
        return None, None
    window = candles[-(lookback + 1):-1]
    if len(window) < 3:
        return None, None
    pivots_low = [
        window[i].low_price
        for i in range(1, len(window) - 1)
        if window[i].low_price <= window[i - 1].low_price
        and window[i].low_price <= window[i + 1].low_price
    ]
    pivots_high = [
        window[i].high_price
        for i in range(1, len(window) - 1)
        if window[i].high_price >= window[i - 1].high_price
        and window[i].high_price >= window[i + 1].high_price
    ]
    current_close = candles[-1].close_price
    support = max((p for p in pivots_low if p <= current_close), default=None)
    resistance = min(
        (p for p in pivots_high if p >= current_close), default=None
    )
    return support, resistance


def breakout_breakdown(
    candles: list[MarketCandle], lookback: int = 20
) -> tuple[bool, bool]:
    """(is_breakout, is_breakdown).

    Breakout when the current close exceeds the highest high of the prior
    `lookback` bars; breakdown when close is below the lowest low.
    """
    if len(candles) < 2:
        return False, False
    prior = candles[-(lookback + 1):-1]
    if not prior:
        return False, False
    prior_high = max(c.high_price for c in prior)
    prior_low = min(c.low_price for c in prior)
    close = candles[-1].close_price
    return close > prior_high, close < prior_low


def gap_pct(candles: list[MarketCandle]) -> float | None:
    """Session gap in percent: (open - prev_close) / prev_close * 100."""
    if len(candles) < 2:
        return None
    prev_close = candles[-2].close_price
    if prev_close <= 0:
        return None
    return (candles[-1].open_price - prev_close) / prev_close * 100.0


def compute_structure(candles: list[MarketCandle]) -> MarketStructure:
    """Compute the full :class:`MarketStructure` for the last bar."""
    pd_high, pd_low = previous_day_high_low(candles)
    wk_high, wk_low = weekly_high_low(candles)
    or_high, or_low = opening_range(candles)
    support, resistance = support_resistance(candles)
    is_breakout, is_breakdown = breakout_breakdown(candles)
    gap = gap_pct(candles)
    return MarketStructure(
        previous_day_high=pd_high,
        previous_day_low=pd_low,
        weekly_high=wk_high,
        weekly_low=wk_low,
        opening_range_high=or_high,
        opening_range_low=or_low,
        support=support,
        resistance=resistance,
        is_breakout=is_breakout,
        is_breakdown=is_breakdown,
        gap_pct=gap,
    )