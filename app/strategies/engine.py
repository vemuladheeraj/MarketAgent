"""Evaluate applicable strategies and score their candidates."""

from __future__ import annotations

from app.config.settings import SignalConfig, StrategyConfig
from app.logging.setup import get_logger, log_event
from app.models.enums import DataQuality
from app.models.trading import Signal
from app.scoring.signal_scorer import SignalScorer
from app.strategies.base.strategy import BaseStrategy, StrategyContext
from app.strategies.implementations import default_strategies


class StrategyEngine:
    """Runs the enabled strategy set against one context snapshot."""

    def __init__(
        self,
        *,
        signal_config: SignalConfig,
        strategy_config: StrategyConfig | None = None,
        strategies: list[BaseStrategy] | None = None,
    ) -> None:
        self.strategies = strategies if strategies is not None else default_strategies()
        self.strategy_config = strategy_config or StrategyConfig()
        self.scorer = SignalScorer(signal_config)
        self._logger = get_logger("strategies")

    def evaluate(
        self,
        context: StrategyContext,
        *,
        data_quality: DataQuality = DataQuality.VALID,
    ) -> list[Signal]:
        if data_quality == DataQuality.INVALID:
            log_event(
                self._logger,
                "SIGNAL_REJECTED",
                "signal engine skipped because data quality is INVALID",
                symbol=context.technical.symbol,
            )
            return []

        results: list[Signal] = []
        extra = {"breadth": max(0.0, min(1.0, (context.breadth_score + 1.0) / 2.0))}
        for strategy in self.strategies:
            if not self._enabled(strategy.name):
                continue
            applicable = strategy.is_applicable(context)
            log_event(
                self._logger,
                "STRATEGY_EVALUATED",
                "strategy evaluated",
                strategy=strategy.name,
                applicable=applicable,
                regime=context.regime.regime.value,
            )
            if not applicable:
                continue
            candidate = strategy.generate_candidate(context)
            if candidate is None:
                continue
            signal = self.scorer.score(
                candidate,
                data_quality=data_quality,
                extra_factors=extra,
            )
            event = "SIGNAL_GENERATED" if signal.accepted else "SIGNAL_REJECTED"
            log_event(
                self._logger,
                event,
                "candidate scored",
                strategy=strategy.name,
                score=signal.score,
                accepted=signal.accepted,
                classification=signal.classification.value,
            )
            results.append(signal)
        return results

    def _enabled(self, name: str) -> bool:
        flags = self.strategy_config.enabled
        if not flags:
            return True
        return flags.get(name, False)
