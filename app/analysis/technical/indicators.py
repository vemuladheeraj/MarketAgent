"""Deterministic technical-indicator implementations.

All implementations are self-contained (no black-box indicator library) so
the maths is auditable and unit-testable against reference calculations.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.models.candle import MarketCandle

#: Number of trading days per year used for annualisation (Indian market).
TRADING_DAYS = 252


def _series(candles: list[MarketCandle]) -> pd.DataFrame:
    """Convert candle models into a tidy DataFrame sorted by time."""
    rows = [
        {
            "timestamp": c.timestamp,
            "open": c.open_price,
            "high": c.high_price,
            "low": c.low_price,
            "close": c.close_price,
            "volume": c.volume,
        }
        for c in candles
    ]
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    return df.sort_values("timestamp").reset_index(drop=True)


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average (NaN until window-1 prior bars)."""
    if window < 1:
        raise ValueError("window must be >= 1")
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average (adjust=False => recursive EMA)."""
    if span < 1:
        raise ValueError("span must be >= 1")
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI."""
    if period < 1:
        raise ValueError("period must be >= 1")
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100.0 - (100.0 / (1.0 + rs))
    out = out.where(avg_loss != 0, 100.0)
    out = out.where(avg_gain != 0, 0.0)
    return out


def macd(series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD (12, 26, 9). Returns (macd, signal, histogram)."""
    ema_fast = ema(series, 12)
    ema_slow = ema(series, 26)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def roc(series: pd.Series, period: int = 10) -> pd.Series:
    """Rate of change in percent."""
    if period < 1:
        raise ValueError("period must be >= 1")
    shifted = series.shift(period)
    return (series / shifted - 1.0) * 100.0


def true_range(candles: list[MarketCandle]) -> pd.Series:
    df = _series(candles)
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr
def atr(candles: list[MarketCandle], period: int = 14) -> pd.Series:
    """Average True Range (Wilder's smoothing)."""
    tr = true_range(candles)
    if period < 1:
        raise ValueError("period must be >= 1")
    return tr.ewm(alpha=1.0 / period, adjust=False).mean()


def adx(
    candles: list[MarketCandle], period: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Wilder's ADX. Returns (adx, plus_di, minus_di)."""
    if period < 1:
        raise ValueError("period must be >= 1")
    df = _series(candles)
    up = df["high"].diff()
    down = -df["low"].diff()

    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(
        np.where((down > up) & (down > 0), down, 0.0), index=df.index
    )

    tr = true_range(candles).rename("tr")
    atr_s = pd.concat([tr, plus_dm.rename("pdm"), minus_dm.rename("mdm")], axis=1).ewm(
        alpha=1.0 / period, adjust=False
    ).mean()
    plus_di = 100.0 * atr_s["pdm"] / atr_s["tr"].replace(0.0, np.nan)
    minus_di = 100.0 * atr_s["mdm"] / atr_s["tr"].replace(0.0, np.nan)

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx_s = dx.ewm(alpha=1.0 / period, adjust=False).mean()
    return adx_s, plus_di, minus_di
def historical_volatility(series: pd.Series, period: int = 20) -> pd.Series:
    """Annualised historical volatility in percent."""
    if period < 1:
        raise ValueError("period must be >= 1")
    log_ret = np.log(series / series.shift(1))
    sample_vol = log_ret.rolling(window=period, min_periods=period).std(ddof=1)
    return sample_vol * np.sqrt(TRADING_DAYS) * 100.0


def bollinger_bands(
    series: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """(lower, mid, upper) Bollinger bands."""
    if period < 1:
        raise ValueError("period must be >= 1")
    mid = sma(series, period)
    std = series.rolling(window=period, min_periods=period).std(ddof=0)
    upper = mid + num_std * std
    lower = mid - num_std * std
    return lower, mid, upper


def vwap(candles: list[MarketCandle]) -> pd.Series:
    """Session VWAP (cumulative typical-price-weighted-by-volume)."""
    df = _series(candles)
    typical = (df["high"] + df["low"] + df["close"]) / 3.0
    pv = (typical * df["volume"]).cumsum()
    vol = df["volume"].cumsum().replace(0.0, np.nan)
    return pv / vol


def relative_volume(candles: list[MarketCandle], lookback: int = 20) -> pd.Series:
    """Current bar volume divided by mean volume of prior `lookback` bars."""
    df = _series(candles)
    avg = df["volume"].shift(1).rolling(window=lookback, min_periods=lookback).mean()
    return df["volume"] / avg.replace(0.0, np.nan)


def volume_spike_mask(
    candles: list[MarketCandle], lookback: int = 20, factor: float = 2.0
) -> pd.Series:
    """True when current volume exceeds `factor` x prior mean volume."""
    df = _series(candles)
    avg = df["volume"].shift(1).rolling(window=lookback, min_periods=lookback).mean()
    return (df["volume"] > factor * avg).fillna(False)
    upper = mid + num_std * std
    lower = mid - num_std * std
    return lower, mid, upper