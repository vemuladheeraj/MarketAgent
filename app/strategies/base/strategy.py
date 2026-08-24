"""Common strategy framework.

Strategies produce research candidates. They do not place trades and do not
claim profitability; scoring, risk, and backtesting decide whether a candidate
is worth further study.

Win-probability used here is an uninformed prior (0.5) until a later phase
calibrates it from out-of-sample history. Expected value is therefore
structural (from R:R and the prior), not a forecast of edge.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ValidationError

from app.analysis.regime import RegimeAssessment
from app.models.enums import Direction, MarketRegime
from app.models.options_analysis import OptionMetrics
from app.models.technical import TechnicalIndicators
from app.models.trading import StrategyCandidate


class StrategyContext(BaseModel):
    """Inputs available to deterministic strategies."""

    technical: TechnicalIndicators
    regime: RegimeAssessment
    options: OptionMetrics | None = None
    breadth_score: float = 0.0


class BaseStrategy(ABC):
    """Strategy contract from the specification."""

    name: str
    preferred_regimes: frozenset[MarketRegime] = frozenset()

    def is_applicable(self, context: StrategyContext) -> bool:
        if not self.preferred_regimes:
            return True
        return context.regime.regime in self.preferred_regimes

    def generate_candidate(self, context: StrategyContext) -> StrategyCandidate | None:
        """Return a candidate or ``None`` when no setup is present."""
        if not self.is_applicable(context) or not self.has_setup(context):
            return None
        direction = self.calculate_direction(context)
        entry = self.calculate_entry(context)
        stop = self.calculate_stop_loss(context)
        targets = self.calculate_targets(context)
        if entry is None or stop is None or not targets:
            return None
        expected_win = abs(targets[0] - entry)
        expected_loss = abs(entry - stop)
        probability = self.uninformed_probability()
        try:
            return StrategyCandidate(
                strategy_name=self.name,
                symbol=context.technical.symbol,
                timestamp=context.technical.timestamp,
                direction=direction,
                entry=entry,
                stop_loss=stop,
                targets=targets,
                invalidation=self.calculate_invalidation(context, direction),
                expected_win=expected_win,
                expected_loss=expected_loss,
                expected_value=self.calculate_expected_value(
                    expected_win, expected_loss, probability
                ),
                probability=probability,
                probability_is_calibrated=False,
                factors=self.factor_scores(context),
                explanation=self.explanation_text(context),
            )
        except (ValidationError, ValueError):
            return None

    def calculate_entry(self, context: StrategyContext) -> float | None:
        return context.technical.close

    def calculate_invalidation(
        self, context: StrategyContext, direction: Direction
    ) -> str:
        if direction == Direction.LONG:
            return "Close below stop or source condition fails"
        return "Close above stop or source condition fails"

    def calculate_expected_value(
        self,
        expected_win: float,
        expected_loss: float,
        probability: float,
    ) -> float:
        """Pre-cost structural EV. Transaction costs are applied by the risk engine."""
        return probability * expected_win - (1.0 - probability) * expected_loss

    def uninformed_probability(self) -> float:
        return 0.5

    def explain(self, candidate: StrategyCandidate) -> str:
        return candidate.explanation

    @abstractmethod
    def has_setup(self, context: StrategyContext) -> bool:
        """True when the strategy's price/OI/structure condition is present."""

    @abstractmethod
    def calculate_direction(self, context: StrategyContext) -> Direction:
        """Intended research direction if a setup exists."""

    @abstractmethod
    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        """Invalidation price. Must sit on the losing side of entry."""

    @abstractmethod
    def calculate_targets(self, context: StrategyContext) -> list[float]:
        """Ordered profit objectives. At least one is required."""

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        return {}

    def explanation_text(self, context: StrategyContext) -> str:
        return self.name
