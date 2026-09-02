"""Enhanced AI Advisor for MarketAgent.

Provides advanced AI-powered trading insights using Google Gemini:
- Explain signals and recommendations in plain English
- Suggest best strategies based on market conditions
- Analyze news and detect contradictions
- Answer trader questions in chat
- Generate action summaries for manual order placement
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config.settings import GeminiConfig
from app.logging.setup import get_logger, log_event
from app.models.snapshots import MarketSnapshot
from app.models.trading import Signal, StrategyCandidate
from app.models.time import now_ist


class EnhancedAIAdvisor:
    """Advanced AI trading advisor using Gemini."""

    def __init__(self, config: GeminiConfig) -> None:
        self.config = config
        self._logger = get_logger("ai.advisor")
        self._client = None
        
        # Initialize Gemini client lazily
        if config.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=config.api_key)
                self._model = config.model or "gemini-2.5-flash"
                log_event(self._logger, "INFO", "Gemini client initialized", model=self._model)
            except Exception as exc:
                log_event(self._logger, "WARNING", "Failed to initialize Gemini client", err=str(exc))

    def explain_signal(self, signal: Signal, market_context: str = "") -> str:
        """Explain a trading signal in plain English.
        
        Input: Strategy candidate with entry, stop, target, and factors
        Output: Natural language explanation for traders
        """
        if not self._client:
            return self._fallback_explain_signal(signal)
        
        try:
            candidate = signal.candidate
            prompt = f"""
You are an expert trading advisor explaining trading signals to retail traders.
Explain this trading signal in simple, actionable terms:

Symbol: {candidate.symbol}
Strategy: {candidate.strategy_name}
Direction: {candidate.direction.value}
Entry Price: {candidate.entry:.2f}
Stop Loss: {candidate.stop_loss:.2f}
Target(s): {', '.join(f'{t:.2f}' for t in candidate.targets)}
Risk: {candidate.expected_loss:.2f}
Reward: {candidate.expected_win:.2f}
Risk/Reward Ratio: 1:{candidate.expected_win/candidate.expected_loss:.2f}
Explanation: {candidate.explanation}
Market Context: {market_context}

Provide a brief (2-3 sentences), clear explanation that:
1. Explains what the signal means in simple terms
2. Specifies the exact entry, stop, and target prices
3. Explains the risk-reward tradeoff
4. Includes any important caveats or risks

Be direct and concise - this is for a trader who needs to make a quick decision.
"""
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            return response.text or self._fallback_explain_signal(signal)
        except Exception as exc:
            self._logger.warning("Gemini explain signal failed: %s", exc)
            return self._fallback_explain_signal(signal)

    def _fallback_explain_signal(self, signal: Signal) -> str:
        """Fallback explanation when Gemini is unavailable."""
        c = signal.candidate
        return (
            f"{c.direction.value} {c.symbol} at {c.entry:.2f}. "
            f"Stop at {c.stop_loss:.2f}, Target {c.targets[0]:.2f}. "
            f"Risk {c.expected_loss:.2f}, Reward {c.expected_win:.2f}. "
            f"{c.explanation}"
        )

    def suggest_best_strategies(
        self, 
        signals: list[Signal], 
        market_regime: str,
        volatility: str,
    ) -> dict[str, Any]:
        """Suggest which strategies are most promising given current market.
        
        Returns:
        {
            "recommended_strategies": ["Strategy 1", "Strategy 2"],
            "rationale": "Why these work now",
            "avoid": ["Strategy 3"],
            "avoid_reason": "Why to skip this",
            "market_fit": "How signal count compares to regime"
        }
        """
        if not self._client:
            return self._fallback_suggest_strategies(signals, market_regime, volatility)
        
        try:
            signal_summary = json.dumps([
                {
                    "strategy": s.candidate.strategy_name,
                    "direction": s.candidate.direction.value,
                    "score": s.score,
                }
                for s in signals
            ], indent=2)
            
            prompt = f"""
You are a quantitative trading advisor helping traders optimize their strategy selection.
Given the current market conditions and available signals, recommend which strategies to focus on.

Market Regime: {market_regime}
Volatility Level: {volatility}
Current Signals: {signal_summary}

Recommend:
1. Which 2-3 strategies are most suitable for this regime
2. Why these work well in {market_regime} markets
3. Which strategies to AVOID right now
4. Brief assessment of signal quality/quantity

Respond in JSON format:
{{
  "recommended_strategies": ["Strategy1", "Strategy2"],
  "rationale": "Why these work now",
  "avoid": ["Strategy3"],
  "avoid_reason": "Why to skip",
  "market_fit": "Quality assessment"
}}
"""
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            try:
                text = response.text or ""
                if text.startswith("```json"):
                    text = text[7:]
                if text.endswith("```"):
                    text = text[:-3]
                return json.loads(text.strip())
            except json.JSONDecodeError:
                return self._fallback_suggest_strategies(signals, market_regime, volatility)
        except Exception as exc:
            self._logger.warning("Gemini strategy suggestion failed: %s", exc)
            return self._fallback_suggest_strategies(signals, market_regime, volatility)

    def _fallback_suggest_strategies(
        self, 
        signals: list[Signal], 
        market_regime: str,
        volatility: str,
    ) -> dict[str, Any]:
        """Fallback strategy suggestions."""
        return {
            "recommended_strategies": [s.candidate.strategy_name for s in signals[:2]] if signals else [],
            "rationale": f"Strategies filtering by {market_regime} regime and {volatility} volatility",
            "avoid": [],
            "avoid_reason": "None identified",
            "market_fit": f"{len(signals)} signals generated"
        }

    def analyze_news_impact(
        self, 
        symbol: str,
        price_change_pct: float,
        news_items: list[str],
        technical_explanation: str = "",
    ) -> str:
        """Correlate news with price movements.
        
        Input: Symbol, price change, news headlines, technical analysis
        Output: Explanation of price move (news-driven vs technical)
        """
        if not self._client or not news_items:
            return self._fallback_news_analysis(symbol, price_change_pct, news_items)
        
        try:
            news_summary = "\n".join(f"- {n}" for n in news_items)
            
            prompt = f"""
You are a financial news analyst helping traders understand price movements.
Analyze the relationship between recent news and price movement for {symbol}.

Recent News:
{news_summary}

Price Movement: {price_change_pct:+.2f}%
Technical Context: {technical_explanation}

In 2-3 sentences, explain:
1. Whether the price move seems justified by the news
2. If this is news-driven or technical
3. Any potential contradictions or surprises

Be concise and direct.
"""
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            return response.text or self._fallback_news_analysis(symbol, price_change_pct, news_items)
        except Exception as exc:
            self._logger.warning("Gemini news analysis failed: %s", exc)
            return self._fallback_news_analysis(symbol, price_change_pct, news_items)

    def _fallback_news_analysis(
        self,
        symbol: str,
        price_change_pct: float,
        news_items: list[str],
    ) -> str:
        """Fallback news analysis."""
        if not news_items:
            return f"{symbol} moved {price_change_pct:+.2f}% with no major news. Technical move."
        return (
            f"{symbol} moved {price_change_pct:+.2f}%. "
            f"Related news items found: {len(news_items)}. "
            f"Review headlines for correlation."
        )

    def detect_contradictions(
        self,
        symbol: str,
        indicators: dict[str, Any],
    ) -> list[str]:
        """Detect contradictions in market signals.
        
        Input: Symbol and key indicators (price, trend, OI, volume, etc.)
        Output: List of identified contradictions/risks
        """
        if not self._client:
            return self._fallback_detect_contradictions(indicators)
        
        try:
            prompt = f"""
You are a quantitative risk analyst identifying market contradictions.
Analyze these indicators for {symbol} and identify any contradictions or warning signs:

{json.dumps(indicators, indent=2)}

List 2-3 key contradictions or risks in a JSON array format:
["Contradiction 1: explanation", "Contradiction 2: explanation", ...]

Only identify REAL contradictions (conflicting signals), not normal market movements.
"""
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            try:
                text = response.text or "[]"
                if text.startswith("```json"):
                    text = text[7:]
                if text.endswith("```"):
                    text = text[:-3]
                return json.loads(text.strip())
            except (json.JSONDecodeError, ValueError):
                return self._fallback_detect_contradictions(indicators)
        except Exception as exc:
            self._logger.warning("Gemini contradiction detection failed: %s", exc)
            return self._fallback_detect_contradictions(indicators)

    def _fallback_detect_contradictions(self, indicators: dict[str, Any]) -> list[str]:
        """Fallback contradiction detection."""
        return []

    def answer_trader_question(self, question: str, market_context: dict[str, Any] = {}) -> str:
        """Answer trader questions about current market conditions.
        
        Input: Natural language question + current market data
        Output: Knowledgeable, concise answer
        """
        if not self._client:
            return "Market context unavailable. Check system status."
        
        try:
            context_str = json.dumps(market_context, indent=2) if market_context else "No context"
            
            prompt = f"""
You are an expert trading advisor for retail options traders.
The trader asks:

"{question}"

Current Market Context:
{context_str}

Respond in 2-3 sentences with:
1. A direct answer to their question
2. Relevant context from current market conditions if applicable
3. Any important caveats or risks to consider

Be concise and actionable.
"""
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            return response.text or "Unable to answer at this time."
        except Exception as exc:
            self._logger.warning("Gemini question answering failed: %s", exc)
            return f"Question: {question}\n\nUnable to answer (AI unavailable). Consult market data directly."

    def generate_action_summary(
        self,
        symbol: str,
        market: str,  # "IN" or "US"
        signals: list[Signal],
        regime: str,
        time_of_day: str,
    ) -> str:
        """Generate an action summary for manual broker order placement.
        
        Returns a formatted string with:
        - Best trade setup
        - Exact entry, stop, target
        - Position sizing hint
        - Broker instructions
        """
        if not signals:
            return f"NO SIGNALS: No trading opportunities identified for {symbol} ({market})."
        
        if not self._client:
            return self._fallback_action_summary(symbol, signals, regime, time_of_day)
        
        try:
            best_signal = sorted(signals, key=lambda s: s.score, reverse=True)[0]
            c = best_signal.candidate
            
            prompt = f"""
You are a trading execution assistant helping retail traders place manual orders.
Generate a clear action summary for this trading setup:

Market: {market} ({'Indian' if market == 'IN' else 'US'}) Options
Time: {time_of_day}
Symbol: {symbol}
Regime: {regime}

Best Signal:
- Strategy: {c.strategy_name}
- Direction: {c.direction.value}
- Entry: {c.entry:.2f}
- Stop Loss: {c.stop_loss:.2f}
- Target: {c.targets[0]:.2f}
- Risk/Reward: 1:{c.expected_win/max(c.expected_loss, 0.01):.2f}
- Confidence: {best_signal.score:.0%}

Generate a concise ACTION SUMMARY that includes:
1. SETUP: Brief description of the trade
2. ENTRY: Exact price and condition
3. STOP: Exact stop price
4. TARGET: Primary profit target
5. POSITION SIZE: Generic guidance (small/medium/large)
6. TIMEFRAME: Holding period estimate
7. BROKER STEPS: Step-by-step instructions for manual order placement

Format for quick reading (5-10 seconds).
"""
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
            )
            return response.text or self._fallback_action_summary(symbol, signals, regime, time_of_day)
        except Exception as exc:
            self._logger.warning("Gemini action summary failed: %s", exc)
            return self._fallback_action_summary(symbol, signals, regime, time_of_day)

    def _fallback_action_summary(
        self,
        symbol: str,
        signals: list[Signal],
        regime: str,
        time_of_day: str,
    ) -> str:
        """Fallback action summary."""
        if not signals:
            return f"No signals for {symbol}"
        
        best = sorted(signals, key=lambda s: s.score, reverse=True)[0]
        c = best.candidate
        
        return f"""
ACTION SUMMARY: {symbol} - {regime} Regime

SETUP: {c.strategy_name} ({c.direction.value})
ENTRY: {c.entry:.2f}
STOP: {c.stop_loss:.2f}
TARGET: {c.targets[0]:.2f}
RATIO: 1:{c.expected_win/max(c.expected_loss, 0.01):.2f}
CONFIDENCE: {best.score:.0%}

BROKER STEPS:
1. Open your options chain for {symbol}
2. Select {'CALL' if c.direction.value == 'LONG' else 'PUT'} option
3. Place order at entry price {c.entry:.2f}
4. Set stop loss at {c.stop_loss:.2f}
5. Set target at {c.targets[0]:.2f}
"""
