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


# ============================================================================
# US MARKET INCOME STRATEGIES (Premium collection, limited risk/reward)
# ============================================================================


class USSmallCapMomentumBreakoutStrategy(BaseStrategy):
    """Fast intraday momentum setup for US equities.

    This is the strategy direction aligned with the user's requirement for
    small-cap and micro-cap US names: trade strong momentum with quick follow-through,
    tight stops, and fast profit targets.
    """

    name = "us_small_cap_momentum"
    preferred_regimes = frozenset({
        MarketRegime.STRONG_UPTREND,
        MarketRegime.UPTREND,
        MarketRegime.NORMAL_VOLATILITY,
    })

    def has_setup(self, context: StrategyContext) -> bool:
        t = context.technical
        if t.sma_20 is None or t.atr_14 is None:
            return False
        if t.close <= t.sma_20:
            return False
        if t.rsi_14 is not None and t.rsi_14 < 55:
            return False
        if not t.volume_confirmation:
            return False
        if t.structure.is_breakout is not True:
            return False
        return True

    def calculate_direction(self, context: StrategyContext) -> Direction:
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        t = context.technical
        if t.atr_14 is None:
            return None
        # Tight risk for fast-moving US small-cap names.
        return t.close - max(0.8 * t.atr_14, t.close * 0.015)

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        t = context.technical
        if t.atr_14 is None:
            return []
        return [t.close + 2.5 * t.atr_14, t.close + 4.0 * t.atr_14]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return {
            "trend": 1.0,
            "momentum": 0.9,
            "volume": 0.9,
            "risk_control": 0.7,
        }

    def explanation_text(self, context: StrategyContext) -> str:
        return (
            "Fast US small-cap breakout: price is trading above its short moving average, "
            "momentum is strong, and the move is confirmed by volume. This is a quick intraday "
            "trend-following setup with a tight stop and rapid upside target."
        )


class CoveredCallStrategy(BaseStrategy):
    """Income strategy: Own shares, sell calls.
    
    Preferred in stable/mildly bullish markets. Generates premium but caps upside.
    Recommended for US markets (SPY, QQQ, etc.).
    """
    
    name = "covered_call"
    preferred_regimes = frozenset({
        MarketRegime.RANGE, 
        MarketRegime.UPTREND,
        MarketRegime.LOW_VOLATILITY,
        MarketRegime.NORMAL_VOLATILITY,
    })

    def has_setup(self, context: StrategyContext) -> bool:
        """Covered call setup: price in stable range, not expected to crash."""
        t = context.technical
        o = context.options
        
        # Need options data for IV assessment
        if o is None or o.oi.pcr is None:
            return False
        
        # Price should be near or above SMA 20 (stable)
        if t.sma_20 is None or t.close < t.sma_20 * 0.98:
            return False
        
        # IV should be reasonable (not extremely low, not extremely high)
        if o.iv is None or o.iv < 0.10 or o.iv > 0.50:
            return False
        
        return True

    def calculate_direction(self, context: StrategyContext) -> Direction:
        """Covered call is effectively bullish (own shares) with capped upside."""
        return Direction.LONG

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        """Stop loss: significant support level or 2 ATRs below."""
        t = context.technical
        if t.atr_14 is None or t.structure.support is None:
            return None
        return min(t.structure.support, t.close - 2 * t.atr_14)

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        """Target: Strike price (where shares get called away) or ATR-based."""
        t = context.technical
        if t.atr_14 is None:
            return []
        
        # Realistic call assignment target (1-2% above current)
        upside_target = t.close * 1.02  # 2% upside capped
        return [upside_target]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        """Rate setup quality."""
        t = context.technical
        o = context.options
        
        trend_score = 0.7 if t.sma_20 and t.close > t.sma_20 else 0.3
        iv_score = min(1.0, (o.iv or 0.20) / 0.25) if o else 0.5  # Higher IV is better
        stability = 0.8  # Assume stable if conditions met
        
        return {
            "trend": trend_score,
            "iv_environment": iv_score,
            "stability": stability,
        }

    def explanation_text(self, context: StrategyContext) -> str:
        return (
            "Covered call income strategy: Own shares, sell calls for premium. "
            "Best in stable to mildly bullish markets. Caps upside but generates income."
        )


class CashSecuredPutStrategy(BaseStrategy):
    """Income strategy: Sell puts, keep cash aside for assignment.
    
    Preferred in stable/mildly bullish markets. Generate premium; willing to own shares.
    Recommended for US markets (SPY, QQQ, etc.).
    """
    
    name = "cash_secured_put"
    preferred_regimes = frozenset({
        MarketRegime.RANGE,
        MarketRegime.UPTREND,
        MarketRegime.LOW_VOLATILITY,
        MarketRegime.NORMAL_VOLATILITY,
    })

    def has_setup(self, context: StrategyContext) -> bool:
        """Cash-secured put setup: price stable, willing to own at lower price."""
        t = context.technical
        o = context.options
        
        # Need options data
        if o is None or o.oi.pcr is None:
            return False
        
        # Price above SMA 20 (not crashing)
        if t.sma_20 is None or t.close < t.sma_20 * 0.97:
            return False
        
        # IV reasonable
        if o.iv is None or o.iv < 0.10 or o.iv > 0.50:
            return False
        
        # PCR not extreme (not too bearish)
        if o.oi.pcr > 1.5:
            return False
        
        return True

    def calculate_direction(self, context: StrategyContext) -> Direction:
        """Cash-secured put is bearish-lite (willing to own at lower price)."""
        return Direction.SHORT

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        """Stop loss: if stock crashes below support significantly."""
        t = context.technical
        if t.structure.support is None or t.atr_14 is None:
            return None
        # Stop at support - 1 ATR
        return max(0, t.structure.support - t.atr_14)

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        """Target: Put strike (where we'd be assigned at) or profit target."""
        t = context.technical
        if t.atr_14 is None:
            return []
        
        # Willing to own at 2-3% below current
        buy_level = t.close * 0.98  # 2% below
        return [buy_level]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        """Rate setup quality."""
        t = context.technical
        o = context.options
        
        trend_score = 0.7 if t.sma_20 and t.close > t.sma_20 else 0.4
        iv_score = min(1.0, (o.iv or 0.20) / 0.25) if o else 0.5
        pcr_score = 0.7 if o and o.oi.pcr and o.oi.pcr < 1.0 else 0.5  # Prefer bullish PCR
        
        return {
            "trend": trend_score,
            "iv_environment": iv_score,
            "sentiment": pcr_score,
        }

    def explanation_text(self, context: StrategyContext) -> str:
        return (
            "Cash-secured put income strategy: Sell puts, keep cash for assignment. "
            "Best in stable to mildly bullish. Generates premium; willing to own shares lower."
        )


class IronCondorStrategy(BaseStrategy):
    """Income strategy: Sell both call and put spreads.
    
    Preferred in range-bound markets. Profits from stable prices.
    Lower risk than naked spreads, limited max profit.
    """
    
    name = "iron_condor"
    preferred_regimes = frozenset({
        MarketRegime.RANGE,
        MarketRegime.LOW_VOLATILITY,
    })

    def has_setup(self, context: StrategyContext) -> bool:
        """Iron condor setup: Stable, ranging market."""
        t = context.technical
        o = context.options
        
        # Need options data
        if o is None or t.atr_14 is None:
            return False
        
        # Price should be in middle of range
        if t.structure.support is None or t.structure.resistance is None:
            return False
        
        range_width = t.structure.resistance - t.structure.support
        price_pct_in_range = (t.close - t.structure.support) / range_width
        
        # Price should be in middle 40-60% of range
        if price_pct_in_range < 0.4 or price_pct_in_range > 0.6:
            return False
        
        return True

    def calculate_direction(self, context: StrategyContext) -> Direction:
        """Iron condor is neutral (profit if price stays between strikes)."""
        return Direction.LONG  # Using LONG as "neutral profit setup"

    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        """Stop loss: if price breaks out of range significantly."""
        t = context.technical
        r = t.structure
        if r.support is None or r.resistance is None:
            return None
        
        # Stop if breaks out of range + 1 ATR buffer
        if t.atr_14 is None:
            return None
        
        range_width = r.resistance - r.support
        # Stop at range breakout + buffer
        return r.support - (range_width * 0.5)

    def calculate_targets(self, context: StrategyContext) -> list[float]:
        """Target: Price stays within range (collect premium)."""
        t = context.technical
        r = t.structure
        
        if r.support is None or r.resistance is None:
            return []
        
        # Midpoint of range is the target
        midpoint = (r.support + r.resistance) / 2
        return [midpoint]

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        """Rate setup quality."""
        t = context.technical
        o = context.options
        
        # Volatility score: Lower IV is better for selling premium
        iv_score = max(0.3, 1.0 - ((o.iv or 0.20) / 0.40)) if o else 0.5
        
        # Range quality: How well-defined is the range?
        if t.structure.support and t.structure.resistance:
            range_health = 0.8
        else:
            range_health = 0.3
        
        return {
            "range_definition": range_health,
            "low_iv_environment": iv_score,
            "neutral_setup": 0.9,
        }

    def explanation_text(self, context: StrategyContext) -> str:
        return (
            "Iron condor income strategy: Sell call + put spreads, profit if price stays between strikes. "
            "Best in range-bound, low-volatility markets. Limited risk and limited reward."
        )


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
        CoveredCallStrategy(),  # US income
        CashSecuredPutStrategy(),  # US income
        IronCondorStrategy(),  # US income
        USSmallCapMomentumBreakoutStrategy(),  # fast US intraday trades
    ]

