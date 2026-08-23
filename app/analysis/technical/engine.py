"""TechnicalAnalyzer — computes the TechnicalIndicators model for a candle series.

Deterministic and repeatable: given the same candles it always produces the
same indicators. The analysis only uses data available *up to and including*
the last bar (no look-ahead).
"""

from __future__ import annotations

import pandas as pd

from app.analysis.technical import indicators as ind
from app.analysis.technical.market_structure import compute_structure
from app.analysis.technical.supertrend import supertrend
from app.models.candle import MarketCandle
from app.models.technical import TechnicalIndicators


class TechnicalAnalyzer:
    """Computes a TechnicalIndicators snapshot for the latest bar."""

    def analyze(
        self,
        candles: list[MarketCandle],
        region: str | None = None,
    ) -> TechnicalIndicators:
        if not candles:
            raise ValueError("cannot analyze an empty candle list")
        df = ind._series(candles)
        closes = df["close"]
        last = candles[-1]

        sma20 = ind.sma(closes, 20)
        sma50 = ind.sma(closes, 50)
        ema9 = ind.ema(closes, 9)
        ema12 = ind.ema(closes, 12)
        ema26 = ind.ema(closes, 26)
        macd_line, signal, hist = ind.macd(closes)
        rsi14 = ind.rsi(closes, 14)
        atr14 = ind.atr(candles, 14)
        st_val, st_dir = supertrend(candles, 10, 3.0)
        adx_s, plus_di, minus_di = ind.adx(candles, 14)
        hv = ind.historical_volatility(closes, 20)
        lo, mid, up = ind.bollinger_bands(closes, 20, 2.0)
        vwap_s = ind.vwap(candles)
        rel_vol = ind.relative_volume(candles, 20)
        spike = ind.volume_spike_mask(candles, 20, 2.0)

        length = len(df) - 1
        structure = compute_structure(candles)

        def _v(s: pd.Series) -> float | None:
            value = s.iloc[length]
            return None if pd.isna(value) else float(value)

        rel_vol_value = _v(rel_vol)
        volume_confirmation = bool(
            rel_vol_value is not None
            and (structure.is_breakout or structure.is_breakdown)
            and rel_vol_value >= 1.5
        )

        return TechnicalIndicators(
            symbol=last.symbol,
            timestamp=last.timestamp,
            close=last.close_price,
            sma_20=_v(sma20),
            sma_50=_v(sma50),
            ema_9=_v(ema9),
            ema_12=_v(ema12),
            ema_26=_v(ema26),
            vwap=_v(vwap_s),
            supertrend_value=_v(st_val),
            supertrend_direction=_v(st_dir),
            rsi_14=_v(rsi14),
            macd=_v(macd_line),
            macd_signal=_v(signal),
            macd_histogram=_v(hist),
            roc_10=_v(ind.roc(closes, 10)),
            atr_14=_v(atr14),
            historical_volatility_20=_v(hv),
            bollinger_lower=_v(lo),
            bollinger_mid=_v(mid),
            bollinger_upper=_v(up),
            adx_14=_v(adx_s),
            plus_di_14=_v(plus_di),
            minus_di_14=_v(minus_di),
            relative_volume=rel_vol_value,
            volume_spike=bool(spike.iloc[length]),
            volume_confirmation=volume_confirmation,
            structure=structure,
        )