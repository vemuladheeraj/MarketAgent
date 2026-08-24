"""Initial deterministic strategy implementations.

These are research templates. They are not optimized and do not imply an
edge. Options-spread strategies currently emit an underlying-level research
candidate (entry/stop/target on the index), not filled option-leg prices.
"""

from __future__ import annotations

from app.models.enums import Direction, MarketRegime
from app.strategies.base.strategy import BaseStrategy, StrategyContext


class OpeningRangeBreakoutStrategy(BaseStrategy):
    name = "opening_range_breakout"
    preferred_regimes = frozenset({MarketRegime.UPTREND, MarketRegime.STRONG_UPTREND})

    def has_setup(self, context: StrategyContext) -> bool:
        t = context.technical
        s = t.structure
        if s.opening_range_high is None or s.opening_range_low is None:
            return False
        return t.close > s.opening_range_high and t.close > s.opening_range_low

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        return context.technical.structure.opening_range_low

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        t = context.technical
        stop = t.structure.opening_range_low
        if stop is None:
            return []
        risk = t.close - stop
        if risk <= 0:
            return []
        return [t.close + risk * 2]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return {
            "price_structure": 1.0,
            "trend": 0.8,
            "volume": 0.6 if context.technical.volume_confirmation else 0.2,
        }

    def explanation_text(self, context: StrategyContext) -> str:
        return "Opening range breakout in a preferred uptrend regime."


class VWAPMomentumStrategy(BaseStrategy):
    name = "vwap_momentum"
    preferred_regimes = frozenset({MarketRegime.UPTREND, MarketRegime.STRONG_UPTREND})

    def has_setup(self, context: StrategyContext) -> bool:
        t = context.technical
        if t.vwap is None or t.atr_14 is None:
            return False
        if t.close <= t.vwap:
            return False
        if t.rsi_14 is not None and t.rsi_14 < 50:
            return False
        return True

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        t = context.technical
        if t.atr_14 is None:
            return None
        return t.close - t.atr_14

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        t = context.technical
        if t.atr_14 is None:
            return []
        return [t.close + 1.8 * t.atr_14]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return {"trend": 0.8, "momentum": 0.8, "volume": 0.4}

    def explanation_text(self, context: StrategyContext) -> str:
        return "Price is above VWAP with supportive momentum."


class TrendContinuationStrategy(BaseStrategy):
    name = "trend_continuation"
    preferred_regimes = frozenset({MarketRegime.UPTREND, MarketRegime.STRONG_UPTREND})

    def has_setup(self, context: StrategyContext) -> bool:
        t = context.technical
        return t.sma_20 is not None and t.atr_14 is not None and t.close > t.sma_20

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        t = context.technical
        if t.sma_20 is None or t.atr_14 is None:
            return None
        return min(t.sma_20, t.close - t.atr_14)

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        t = context.technical
        if t.atr_14 is None:
            return []
        return [t.close + 2 * t.atr_14]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return {"trend": 1.0, "momentum": 0.5, "volatility": 0.4}

    def explanation_text(self, context: StrategyContext) -> str:
        return "Trend continuation candidate above the short moving average."


class SupportResistanceReversalStrategy(BaseStrategy):
    name = "support_resistance_reversal"
    preferred_regimes = frozenset({MarketRegime.RANGE})

    def has_setup(self, context: StrategyContext) -> bool:
        t = context.technical
        s = t.structure
        if s.support is None or s.resistance is None:
            return False
        distance_to_support = abs(t.close - s.support) / t.close
        if distance_to_support > 0.01:
            return False
        if t.rsi_14 is not None and t.rsi_14 > 45:
            return False
        return True

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        support = context.technical.structure.support
        if support is None:
            return None
        return support * 0.995

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        resistance = context.technical.structure.resistance
        return [] if resistance is None else [resistance]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return {"price_structure": 0.8, "momentum": 0.4}

    def explanation_text(self, context: StrategyContext) -> str:
        return "Range-regime reversal candidate near support."


class OIPriceConfirmationStrategy(BaseStrategy):
    name = "oi_price_confirmation"
    preferred_regimes = frozenset({MarketRegime.UPTREND, MarketRegime.STRONG_UPTREND})

    def has_setup(self, context: StrategyContext) -> bool:
        t = context.technical
        o = context.options
        if o is None or t.atr_14 is None:
            return False
        bullish_pcr = o.oi.pcr is not None and o.oi.pcr >= 1.0
        return bullish_pcr and t.close > (t.sma_20 or 0)

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        t = context.technical
        if t.atr_14 is None:
            return None
        return t.close - t.atr_14

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        t = context.technical
        if t.atr_14 is None:
            return []
        return [t.close + 1.7 * t.atr_14]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return {"oi": 0.8, "options_structure": 0.6, "trend": 0.5}

    def explanation_text(self, context: StrategyContext) -> str:
        return "Price trend is supported by option-chain OI context. OI is not a directional predictor on its own."


class BreakoutVolumeConfirmationStrategy(BaseStrategy):
    name = "breakout_volume_confirmation"
    preferred_regimes = frozenset({MarketRegime.UPTREND, MarketRegime.STRONG_UPTREND})

    def has_setup(self, context: StrategyContext) -> bool:
        t = context.technical
        return bool(t.structure.is_breakout and t.volume_confirmation and t.atr_14 is not None)

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        t = context.technical
        if t.atr_14 is None:
            return None
        return t.close - t.atr_14

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        t = context.technical
        if t.atr_14 is None:
            return []
        return [t.close + 2.2 * t.atr_14]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return {"price_structure": 1.0, "volume": 1.0, "trend": 0.6}

    def explanation_text(self, context: StrategyContext) -> str:
        return "Breakout is confirmed by relative volume."


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"
    preferred_regimes = frozenset({MarketRegime.RANGE, MarketRegime.LOW_VOLATILITY})

    def has_setup(self, context: StrategyContext) -> bool:
        t = context.technical
        if t.bollinger_lower is None or t.bollinger_mid is None:
            return False
        if t.close > t.bollinger_lower:
            return False
        if t.rsi_14 is not None and t.rsi_14 > 35:
            return False
        return True

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        return context.technical.close * 0.99

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        mid = context.technical.bollinger_mid
        return [] if mid is None else [mid]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return {"momentum": 0.5, "volatility": 0.5, "price_structure": 0.5}

    def explanation_text(self, context: StrategyContext) -> str:
        return "Range/low-volatility mean reversion candidate."


class BullCallSpreadStrategy(BaseStrategy):
    name = "bull_call_spread"
    preferred_regimes = frozenset(
        {MarketRegime.UPTREND, MarketRegime.STRONG_UPTREND, MarketRegime.HIGH_VOLATILITY}
    )

    def has_setup(self, context: StrategyContext) -> bool:
        t = context.technical
        if context.options is None or t.atr_14 is None:
            return False
        return t.close > (t.sma_20 or 0)

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        t = context.technical
        if t.atr_14 is None:
            return None
        return t.close - t.atr_14

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        t = context.technical
        if t.atr_14 is None:
            return []
        return [t.close + 1.5 * t.atr_14]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return {"options_structure": 0.8, "trend": 0.6, "volatility": 0.6}

    def explanation_text(self, context: StrategyContext) -> str:
        return "Defined-risk bullish options-spread research candidate (underlying reference, not filled legs)."


class BearPutSpreadStrategy(BaseStrategy):
    name = "bear_put_spread"
    preferred_regimes = frozenset(
        {MarketRegime.DOWNTREND, MarketRegime.STRONG_DOWNTREND, MarketRegime.HIGH_VOLATILITY}
    )

    def has_setup(self, context: StrategyContext) -> bool:
        t = context.technical
        if context.options is None or t.atr_14 is None:
            return False
        return t.close < (t.sma_20 or t.close)

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.SHORT

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        t = context.technical
        if t.atr_14 is None:
            return None
        return t.close + t.atr_14

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        t = context.technical
        if t.atr_14 is None:
            return []
        return [t.close - 1.5 * t.atr_14]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return {"options_structure": 0.8, "trend": 0.6, "volatility": 0.6}

    def explanation_text(self, context: StrategyContext) -> str:
        return "Defined-risk bearish options-spread research candidate (underlying reference, not filled legs)."


def default_strategies() -> list[BaseStrategy]:
    return [
        OpeningRangeBreakoutStrategy(),
        VWAPMomentumStrategy(),
        TrendContinuationStrategy(),
        SupportResistanceReversalStrategy(),
        OIPriceConfirmationStrategy(),
        BreakoutVolumeConfirmationStrategy(),
        MeanReversionStrategy(),
        BullCallSpreadStrategy(),
        BearPutSpreadStrategy(),
    ]
