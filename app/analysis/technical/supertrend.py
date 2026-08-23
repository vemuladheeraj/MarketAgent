"""Supertrend indicator (ATR-based trailing stop)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.analysis.technical.indicators import _series, atr
from app.models.candle import MarketCandle


def supertrend(
    candles: list[MarketCandle], period: int = 10, multiplier: float = 3.0
) -> tuple[pd.Series, pd.Series]:
    """Return (supertrend_value, direction) where direction is +1/-1.

    Follows the canonical Supertrend construction:
      basic_upper = (high + low) / 2 + mult * ATR
      basic_lower = (high + low) / 2 - mult * ATR
    Final bands respect the previous final band to avoid whipsaw, and the
    direction flips when price crosses the active band.
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    df = _series(candles)
    hl2 = (df["high"] + df["low"]) / 2.0
    atr_s = atr(candles, period)

    basic_upper = hl2 + multiplier * atr_s
    basic_lower = hl2 - multiplier * atr_s

    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    direction = pd.Series(1, index=df.index)

    for i in range(len(df)):
        if i == 0:
            final_upper.iloc[i] = basic_upper.iloc[i] if np.isfinite(basic_upper.iloc[i]) else np.nan
            final_lower.iloc[i] = basic_lower.iloc[i] if np.isfinite(basic_lower.iloc[i]) else np.nan
            continue
        prev_fu = final_upper.iloc[i - 1]
        prev_fl = final_lower.iloc[i - 1]
        bu = basic_upper.iloc[i] if np.isfinite(basic_upper.iloc[i]) else np.nan
        bl = basic_lower.iloc[i] if np.isfinite(basic_lower.iloc[i]) else np.nan

        if np.isnan(prev_fu) or np.isnan(prev_fl):
            continue

        if bu < prev_fu or df["close"].iloc[i - 1] > prev_fu:
            final_upper.iloc[i] = bu
        else:
            final_upper.iloc[i] = prev_fu

        if bl > prev_fl or df["close"].iloc[i - 1] < prev_fl:
            final_lower.iloc[i] = bl
        else:
            final_lower.iloc[i] = prev_fl

        prev_dir = -1 if i >= 2 and direction.iloc[i - 1] == -1 else 1
        if df["close"].iloc[i] < final_upper.iloc[i] and prev_dir == 1:
            direction.iloc[i] = -1
        elif df["close"].iloc[i] > final_lower.iloc[i] and prev_dir == -1:
            direction.iloc[i] = 1
        else:
            direction.iloc[i] = prev_dir

    band = pd.Series(
        np.where(direction == 1, final_lower, final_upper),
        index=df.index,
    )
    return band, direction