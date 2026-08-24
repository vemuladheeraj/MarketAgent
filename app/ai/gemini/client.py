"""Gemini AI contextual interpretation and reasoning layer.

Provides contextual explanations, identifies cross-factor contradictions,
and synthesizes quantitative market states into structured reasoning artifacts.
Never invents data, fabricates statistics, or overrides risk controls.
"""

from __future__ import annotations

import json
from typing import Any

from app.ai.contradictions import ContradictionDetector
from app.config.settings import GeminiConfig
from app.logging.setup import get_logger, log_event
from app.models.ai import Contradiction, GeminiAnalysis, NewsItem
from app.models.enums import MarketRegime
from app.models.options_analysis import OptionMetrics
from app.models.risk import RiskAssessment
from app.models.snapshots import BreadthSnapshot
from app.models.technical import TechnicalIndicators
from app.models.time import now_ist
from app.models.trading import Signal


class GeminiClient:
    """Client for structured market reasoning and explanation."""

    def __init__(
        self,
        config: GeminiConfig,
        *,
        contradiction_detector: ContradictionDetector | None = None,
    ) -> None:
        self.config = config
        self.detector = contradiction_detector or ContradictionDetector()
        self._logger = get_logger("ai.gemini")

    def analyze_market(
        self,
        *,
        technical: TechnicalIndicators,
        regime: Any,  # RegimeAssessment
        options: OptionMetrics | None = None,
        breadth: BreadthSnapshot | None = None,
        signals: list[Signal] | None = None,
        risk: RiskAssessment | None = None,
        news: list[NewsItem] | None = None,
    ) -> GeminiAnalysis:
        """Produce structured contextual analysis grounded strictly in quantitative inputs."""
        # 1. Run deterministic contradiction detection
        contradictions = self.detector.analyze(
            technical=technical,
            regime=regime,
            options=options,
            breadth=breadth,
            signals=signals,
        )

        grounded_data = self._build_grounded_summary(
            technical=technical,
            regime=regime,
            options=options,
            breadth=breadth,
            signals=signals,
            risk=risk,
            news=news,
        )

        # 2. If API Key is configured, attempt remote Gemini reasoning call
        if self.config.api_key:
            try:
                analysis = self._call_gemini_api(
                    grounded_data=grounded_data,
                    contradictions=contradictions,
                    symbol=technical.symbol,
                )
                if analysis is not None:
                    log_event(
                        self._logger,
                        "GEMINI_ANALYSIS_COMPLETED",
                        "gemini contextual reasoning generated",
                        symbol=technical.symbol,
                        bias=analysis.market_bias,
                        contradictions=len(contradictions),
                    )
                    return analysis
            except Exception as exc:  # noqa: BLE001
                log_event(
                    self._logger,
                    "ERROR",
                    "gemini api call failed; falling back to deterministic synthesis",
                    err=str(exc),
                )

        # 3. Fallback: Deterministic quantitative synthesis
        fallback = self._deterministic_synthesis(
            technical=technical,
            regime=regime,
            options=options,
            breadth=breadth,
            signals=signals,
            risk=risk,
            news=news,
            contradictions=contradictions,
            grounded_data=grounded_data,
        )
        log_event(
            self._logger,
            "GEMINI_ANALYSIS_COMPLETED",
            "deterministic analysis synthesized (offline/fallback)",
            symbol=technical.symbol,
            bias=fallback.market_bias,
            contradictions=len(contradictions),
        )
        return fallback

    def _build_grounded_summary(
        self,
        *,
        technical: TechnicalIndicators,
        regime: Any,
        options: OptionMetrics | None,
        breadth: BreadthSnapshot | None,
        signals: list[Signal] | None,
        risk: RiskAssessment | None,
        news: list[NewsItem] | None,
    ) -> dict[str, Any]:
        return {
            "symbol": technical.symbol,
            "timestamp": technical.timestamp.isoformat(),
            "close": technical.close,
            "sma_20": technical.sma_20,
            "sma_50": technical.sma_50,
            "rsi_14": technical.rsi_14,
            "supertrend_direction": technical.supertrend_direction,
            "adx_14": technical.adx_14,
            "is_breakout": technical.structure.is_breakout,
            "volume_confirmation": technical.volume_confirmation,
            "regime": regime.regime.value if hasattr(regime.regime, "value") else str(regime.regime),
            "regime_confidence": getattr(regime, "confidence", 0.5),
            "pcr": options.oi.pcr if options else None,
            "call_resistance": options.oi.call_resistance if options else None,
            "put_support": options.oi.put_support if options else None,
            "breadth_adr": breadth.advance_decline_ratio if breadth else None,
            "accepted_signals_count": sum(1 for s in (signals or []) if s.accepted),
            "risk_approved": risk.approved if risk else None,
            "news_count": len(news or []),
        }

    def _deterministic_synthesis(
        self,
        *,
        technical: TechnicalIndicators,
        regime: Any,
        options: OptionMetrics | None,
        breadth: BreadthSnapshot | None,
        signals: list[Signal] | None,
        risk: RiskAssessment | None,
        news: list[NewsItem] | None,
        contradictions: list[Contradiction],
        grounded_data: dict[str, Any],
    ) -> GeminiAnalysis:
        regime_val = regime.regime if hasattr(regime, "regime") else MarketRegime.UNCERTAIN
        regime_name = regime_val.value if hasattr(regime_val, "value") else str(regime_val)

        # Determine bias
        if "uptrend" in regime_name:
            bias = "BULLISH"
        elif "downtrend" in regime_name:
            bias = "BEARISH"
        elif "range" in regime_name or "volatility" in regime_name:
            bias = "NEUTRAL"
        else:
            bias = "UNCERTAIN"

        key_factors: list[str] = [
            f"Regime is classified as {regime_name.upper()} (confidence: {getattr(regime, 'confidence', 0.5):.2f})",
            f"Close is {technical.close:.2f} relative to SMA20 ({technical.sma_20})",
        ]
        if technical.rsi_14 is not None:
            key_factors.append(f"RSI(14) is {technical.rsi_14:.1f}")

        supporting_factors: list[str] = []
        if technical.supertrend_direction == 1:
            supporting_factors.append("Supertrend is bullish")
        elif technical.supertrend_direction == -1:
            supporting_factors.append("Supertrend is bearish")

        if options and options.oi.pcr is not None:
            supporting_factors.append(f"Option Chain PCR is {options.oi.pcr:.2f}")

        conflicting_factors = [c.description for c in contradictions]

        risks: list[str] = []
        if contradictions:
            risks.append(f"Found {len(contradictions)} cross-factor contradiction(s) requiring caution")
        if technical.structure.is_breakout and not technical.volume_confirmation:
            risks.append("Unconfirmed breakout carries higher failure probability")

        accepted_sig = [s for s in (signals or []) if s.accepted]
        if accepted_sig:
            sig_text = f"{len(accepted_sig)} valid setup(s) accepted ({', '.join(s.candidate.strategy_name for s in accepted_sig)})."
        else:
            sig_text = "No candidate setups met acceptance criteria (NO_TRADE state)."

        summary = (
            f"{technical.symbol} is currently in a {regime_name} regime at price {technical.close:.2f}. "
            f"{sig_text}"
        )

        return GeminiAnalysis(
            symbol=technical.symbol,
            timestamp=technical.timestamp,
            summary=summary,
            market_bias=bias,
            key_factors=key_factors,
            supporting_factors=supporting_factors,
            conflicting_factors=conflicting_factors,
            risks=risks,
            signal_interpretation=sig_text,
            confidence=round(getattr(regime, "confidence", 0.5), 2),
            explanation="Synthesized deterministically from verified quantitative indicators.",
            contradictions=contradictions,
            grounded_data_summary=grounded_data,
        )

    def _call_gemini_api(
        self,
        *,
        grounded_data: dict[str, Any],
        contradictions: list[Contradiction],
        symbol: str,
    ) -> GeminiAnalysis | None:
        """Call external Gemini SDK with strictly structured schema."""
        # Optional external SDK integration if installed
        try:
            prompt = (
                f"You are the interpretation layer for an Indian market research system.\n"
                f"Analyze the following verified quantitative market data for {symbol}:\n"
                f"Data: {json.dumps(grounded_data)}\n"
                f"Contradictions: {json.dumps([c.model_dump() for c in contradictions])}\n\n"
                f"Provide a structured JSON response with fields: summary, market_bias (BULLISH/BEARISH/NEUTRAL/UNCERTAIN), "
                f"key_factors, supporting_factors, conflicting_factors, risks, signal_interpretation, confidence (0.0 to 1.0), explanation.\n"
                f"CRITICAL: Do NOT invent or hallucinate any numbers. Every number must match the input."
            )

            try:
                from google import genai
                client = genai.Client(api_key=self.config.api_key)
                model_name = self.config.model or "gemini-2.5-flash"
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = (response.text or "").strip()
            except ImportError:
                import google.generativeai as genai_legacy  # type: ignore
                genai_legacy.configure(api_key=self.config.api_key)
                model_name = self.config.model or "gemini-1.5-flash"
                model = genai_legacy.GenerativeModel(model_name)
                response = model.generate_content(prompt)
                text = (response.text or "").strip()
            # Clean possible markdown wrapping
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            parsed = json.loads(text.strip())

            def _to_str_list(items: Any) -> list[str]:
                if not isinstance(items, list):
                    return [str(items)] if items else []
                res = []
                for item in items:
                    if isinstance(item, dict):
                        val = item.get("factor") or item.get("risk") or item.get("description") or item.get("text") or str(item)
                        res.append(str(val))
                    else:
                        res.append(str(item))
                return res

            return GeminiAnalysis(
                symbol=symbol,
                timestamp=now_ist(),
                summary=parsed.get("summary", ""),
                market_bias=parsed.get("market_bias", "UNCERTAIN"),
                key_factors=_to_str_list(parsed.get("key_factors", [])),
                supporting_factors=_to_str_list(parsed.get("supporting_factors", [])),
                conflicting_factors=_to_str_list(parsed.get("conflicting_factors", [])),
                risks=_to_str_list(parsed.get("risks", [])),
                signal_interpretation=parsed.get("signal_interpretation", ""),
                confidence=float(parsed.get("confidence", 0.5)),
                explanation=parsed.get("explanation", ""),
                contradictions=contradictions,
                grounded_data_summary=grounded_data,
            )
        except Exception as exc:
            self._logger.warning("Gemini remote call failed: %s", exc)
            return None
