"""Deterministic Contradiction Detector.

Identifies quantitative cross-factor contradictions (e.g., Bullish Price vs Bearish Option OI,
Breakout without Volume Confirmation, Price vs Breadth Divergence).
"""

from __future__ import annotations

from app.analysis.regime.classifier import RegimeAssessment
from app.models.ai import Contradiction
from app.models.enums import MarketRegime
from app.models.options_analysis import OptionMetrics
from app.models.snapshots import BreadthSnapshot
from app.models.technical import TechnicalIndicators
from app.models.trading import Signal


class ContradictionDetector:
    """Finds conflicting signals and factors across market layers."""

    def analyze(
        self,
        *,
        technical: TechnicalIndicators,
        regime: RegimeAssessment,
        options: OptionMetrics | None = None,
        breadth: BreadthSnapshot | None = None,
        signals: list[Signal] | None = None,
    ) -> list[Contradiction]:
        contradictions: list[Contradiction] = []

        # 1. Technical Bullish vs Options Call Resistance / Bearish PCR
        is_tech_bullish = (
            technical.sma_20 is not None
            and technical.close > technical.sma_20
            and (technical.supertrend_direction or 1) > 0
        )
        is_tech_bearish = (
            technical.sma_20 is not None
            and technical.close < technical.sma_20
            and (technical.supertrend_direction or -1) < 0
        )

        if options is not None:
            # Bullish price into heavy call resistance
            if is_tech_bullish and options.oi.call_resistance is not None:
                if options.oi.call_resistance <= technical.close * 1.002:
                    contradictions.append(
                        Contradiction(
                            factor_a="Technical Bullish Trend",
                            factor_b="Option Chain Call Resistance",
                            description=f"Price ({technical.close:.1f}) is right at or above major Call resistance strike ({options.oi.call_resistance:.1f}), posing overhead supply risk.",
                            severity="HIGH",
                        )
                    )

            # Bullish price with bearish PCR
            if is_tech_bullish and options.oi.pcr is not None and options.oi.pcr < 0.70:
                contradictions.append(
                    Contradiction(
                        factor_a="Technical Bullish Trend",
                        factor_b="Option Chain Low PCR",
                        description=f"Bullish technical posture contradicts low Put-Call Ratio ({options.oi.pcr:.2f} < 0.70), indicating heavy call writing.",
                        severity="MEDIUM",
                    )
                )

            # Bearish price into strong put support
            if is_tech_bearish and options.oi.put_support is not None:
                if options.oi.put_support >= technical.close * 0.998:
                    contradictions.append(
                        Contradiction(
                            factor_a="Technical Bearish Trend",
                            factor_b="Option Chain Put Support",
                            description=f"Price ({technical.close:.1f}) is testing major Put support strike ({options.oi.put_support:.1f}), posing downside stalling risk.",
                            severity="HIGH",
                        )
                    )

            # Bearish price with high PCR
            if is_tech_bearish and options.oi.pcr is not None and options.oi.pcr > 1.35:
                contradictions.append(
                    Contradiction(
                        factor_a="Technical Bearish Trend",
                        factor_b="Option Chain High PCR",
                        description=f"Bearish technical posture contradicts elevated Put-Call Ratio ({options.oi.pcr:.2f} > 1.35), indicating possible put seller support.",
                        severity="MEDIUM",
                    )
                )

        # 2. Breakout without Volume Confirmation
        if technical.structure.is_breakout and not technical.volume_confirmation:
            contradictions.append(
                Contradiction(
                    factor_a="Price Structure Breakout",
                    factor_b="Volume Confirmation Missing",
                    description="Price broke above key structural level but relative volume did not confirm, indicating elevated false-breakout risk.",
                    severity="HIGH",
                )
            )

        if technical.structure.is_breakdown and not technical.volume_confirmation:
            contradictions.append(
                Contradiction(
                    factor_a="Price Structure Breakdown",
                    factor_b="Volume Confirmation Missing",
                    description="Price broke below key structural level without supporting volume confirmation.",
                    severity="MEDIUM",
                )
            )

        # 3. Regime Strength vs ADX
        if regime.regime in (MarketRegime.STRONG_UPTREND, MarketRegime.STRONG_DOWNTREND):
            if technical.adx_14 is not None and technical.adx_14 < 20.0:
                contradictions.append(
                    Contradiction(
                        factor_a="Strong Trend Regime Classification",
                        factor_b="Low ADX Trend Strength",
                        description=f"Market regime indicates strong trend, but ADX ({technical.adx_14:.1f}) is below 20.0, indicating weak directional momentum.",
                        severity="MEDIUM",
                    )
                )

        # 4. Price Trend vs Breadth Divergence
        if breadth is not None and breadth.total > 0:
            adr = breadth.advance_decline_ratio
            if is_tech_bullish and adr is not None and adr < 0.6:
                contradictions.append(
                    Contradiction(
                        factor_a="Index Bullish Price",
                        factor_b="Negative Market Breadth",
                        description=f"Index is bullish but market breadth is heavily negative (A/D ratio {adr:.2f} < 0.60), showing narrow participation.",
                        severity="HIGH",
                    )
                )
            elif is_tech_bearish and adr is not None and adr > 1.7:
                contradictions.append(
                    Contradiction(
                        factor_a="Index Bearish Price",
                        factor_b="Positive Market Breadth",
                        description=f"Index is falling but broader market breadth is strongly positive (A/D ratio {adr:.2f} > 1.70).",
                        severity="MEDIUM",
                    )
                )

        return contradictions
