"""Common strategy framework.

Strategies produce research candidates. They do not place trades and do not
claim profitability; scoring, risk, and backtesting decide whether a candidate
is worth further study.

Win-probability used here is an uninformed prior (0.5) until a later phase
calibrates it from out-of-sample history. Expected value is therefore
structural (from R:R and the prior), not a forecast of edge.

🎓 BEGINNER GUIDE TO STRATEGIES:
================================
A "strategy" is a rule-based system for detecting trading opportunities.
Think of it like a recipe: IF (condition 1 AND condition 2), THEN generate
trading idea with specific entry/stop/target.

Example: Opening Range Breakout Strategy
  IF (price closes above today's opening hour high) AND (we're in uptrend):
    ENTRY: Current close price
    STOP_LOSS: Opening hour low
    TARGET: Entry + 2× the distance to stop loss

The system evaluates this deterministically (no guessing). If the conditions
match, a "StrategyCandidate" is created and scored. The score determines
whether to show it to the trader (NO_TRADE, CAUTION, BUY, STRONG_BUY, etc).
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
    """Inputs available to deterministic strategies.
    
    Think of this as the "data package" passed to each strategy for evaluation.
    Every strategy receives:
      - technical: Price, moving averages, RSI, MACD, ATR, etc. (technical indicators)
      - regime: Market trend (up/down/range), volatility level, event risk
      - options: Greeks, IV, PCR, OI concentration (if options analysis available)
      - breadth_score: Health of the broader market (how many stocks up vs down)
    """

    technical: TechnicalIndicators
    regime: RegimeAssessment
    options: OptionMetrics | None = None
    breadth_score: float = 0.0


class BaseStrategy(ABC):
    """Strategy contract from the specification.
    
    🎓 HOW STRATEGIES WORK:
    ======================
    1. is_applicable()
       Check if this strategy's preferred market regime matches the current regime.
       Example: "Opening Range Breakout" only works in an UPTREND.
       In a DOWNTREND? This strategy won't generate a signal.
    
    2. has_setup()
       Check if the price/indicator conditions are met.
       Example: Price must close ABOVE opening hour high.
       If not, no signal.
    
    3. calculate_entry()
       At what price should the trader enter?
       Usually = current close price.
    
    4. calculate_stop_loss()
       At what price should the trader exit to avoid losses?
       This is the "invalidation" level.
       Example: "If price falls below opening hour low, I was wrong."
    
    5. calculate_targets()
       At what price should the trader take profit?
       Usually at least 1 target (can have multiple).
       Example: Entry ₹25,000 + 2× risk = ₹25,500 profit target.
    
    6. factor_scores()
       How confident is the setup? Rate different factors (trend, volume, etc).
       Example: trend=0.8 (strong), volume=0.6 (moderate).
       These scores are used to rate the overall recommendation.
    
    7. generate_candidate()
       If all checks pass, create a StrategyCandidate (trading idea).
       Otherwise return None (no signal today).
    
    Example workflow:
    ┌─────────────────────────────────────┐
    │ DATA ARRIVES: NIFTY 25432, RSI 68   │
    └─────────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────┐
    │ is_applicable()?                    │
    │ (UPTREND regime?) YES ✓             │
    └─────────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────┐
    │ has_setup()?                        │
    │ (Price > opening high?) YES ✓       │
    └─────────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────┐
    │ Calculate entry, SL, targets        │
    │ Entry: 25432                        │
    │ SL: 25200                           │
    │ Target: 25662                       │
    └─────────────────────────────────────┘
                    │
                    ▼
    ┌─────────────────────────────────────┐
    │ Create StrategyCandidate            │
    │ → Sent to scorer for rating         │
    │ → Scorer may rate it: STRONG_BUY    │
    └─────────────────────────────────────┘
    """

    name: str
    preferred_regimes: frozenset[MarketRegime] = frozenset()

    def is_applicable(self, context: StrategyContext) -> bool:
        """Should this strategy even be considered right now?
        
        Returns False if:
        - The strategy has preferred regimes (e.g., only works in uptrend)
        - Current regime doesn't match
        
        Returns True if:
        - No preferred regimes (works in any condition)
        - Current regime is in the preferred list
        """
        if not self.preferred_regimes:
            return True
        return context.regime.regime in self.preferred_regimes

    def generate_candidate(self, context: StrategyContext) -> StrategyCandidate | None:
        """Return a trading idea (candidate) or None if no setup exists.
        
        This is the main entry point. It:
        1. Checks if the strategy is applicable to current regime
        2. Checks if the setup conditions are met (has_setup)
        3. Calculates entry, stop-loss, and profit targets
        4. Computes expected value (win × probability - loss × probability)
        5. Returns a StrategyCandidate with all details
        
        Returns None if any step fails (e.g., setup not present).
        """
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
        """At what price should the trade be entered?
        
        Default: Current close price (now).
        
        Override if your strategy needs a different entry:
        Example: Buy only if price dips to 50-day moving average.
        """
        return context.technical.close

    def calculate_invalidation(
        self, context: StrategyContext, direction: Direction
    ) -> str:
        """Message explaining when this trade idea is WRONG.
        
        LONG trades:
        - Close below stop loss = idea was wrong
        - Source condition fails = idea was wrong
        
        SHORT trades:
        - Close above stop loss = idea was wrong
        """
        if direction == Direction.LONG:
            return "Close below stop or source condition fails"
        return "Close above stop or source condition fails"

    def calculate_expected_value(
        self,
        expected_win: float,
        expected_loss: float,
        probability: float,
    ) -> float:
        """Calculate expected value BEFORE costs.
        
        Formula: (Probability × Win) - ((1 - Probability) × Loss)
        
        Example:
          Prob = 0.5 (50% - uninformed prior)
          Win = ₹500 if trade succeeds
          Loss = ₹300 if trade fails
          EV = (0.5 × 500) - (0.5 × 300) = 250 - 150 = +100
          
        Positive EV = might be worth trading (after costs).
        Negative EV = avoid this trade.
        
        Transaction costs (brokerage, taxes, slippage) are deducted by the
        risk engine AFTER this calculation.
        """
        return probability * expected_win - (1.0 - probability) * expected_loss

    def uninformed_probability(self) -> float:
        """Default win probability when we haven't calibrated the strategy yet.
        
        Returns 0.5 (50%) — completely uninformed guess.
        
        Later phases will calibrate this from backtesting results.
        Then a good strategy might return 0.55+ (55%+ win rate).
        """
        return 0.5

    def explain(self, candidate: StrategyCandidate) -> str:
        """Plain-English explanation of why this signal was generated."""
        return candidate.explanation

    @abstractmethod
    def has_setup(self, context: StrategyContext) -> bool:
        """IMPLEMENT THIS: Check if the strategy's condition is present.
        
        Return True if:
        - Price condition met (e.g., price > opening high)
        - Indicator condition met (e.g., RSI > 50)
        - OI/structure condition met (e.g., call OI > put OI)
        
        Return False if:
        - Condition not met → no signal for today
        
        Example:
        ```python
        def has_setup(self, context: StrategyContext) -> bool:
            # "Opening range breakout" requires price to close above opening high
            if context.technical.structure.opening_range_high is None:
                return False
            return context.technical.close > context.technical.structure.opening_range_high
        ```
        """

    @abstractmethod
    def calculate_direction(self, context: StrategyContext) -> Direction:
        """IMPLEMENT THIS: Which direction? LONG (buy) or SHORT (sell)?
        
        LONG = I think price will go UP
               → Buy option calls / sell puts / long underlying
        
        SHORT = I think price will go DOWN
                → Buy option puts / sell calls / short underlying
        
        Example:
        ```python
        def calculate_direction(self, context: StrategyContext) -> Direction:
            return Direction.LONG  # We believe in uptrend
        ```
        """

    @abstractmethod
    def calculate_stop_loss(self, context: StrategyContext) -> float | None:
        """IMPLEMENT THIS: At what price is this trade WRONG?
        
        The "stop loss" or "invalidation" level.
        If price reaches this, exit the trade immediately.
        
        Rules:
        - For LONG trades: stop must be BELOW entry
        - For SHORT trades: stop must be ABOVE entry
        
        Return None if stop-loss cannot be calculated.
        
        Example (Opening Range Breakout):
        ```python
        def calculate_stop_loss(self, context: StrategyContext) -> float | None:
            # Stop at opening hour low
            return context.technical.structure.opening_range_low
        ```
        """

    @abstractmethod
    def calculate_targets(self, context: StrategyContext) -> list[float]:
        """IMPLEMENT THIS: Where should I take profit?
        
        Return a list of price targets (at least 1 required).
        Can have multiple targets: [25500, 25700, 25900]
        
        Usually targets are:
        - Entry + 1× risk (conservative)
        - Entry + 2× risk (moderate)
        - Entry + 3× risk (aggressive)
        
        Return empty list [] if targets cannot be calculated.
        
        Example:
        ```python
        def calculate_targets(self, context: StrategyContext) -> list[float]:
            t = context.technical
            stop = t.structure.opening_range_low
            if stop is None:
                return []
            risk = t.close - stop
            return [t.close + 2 * risk]  # 2× risk as target
        ```
        """

    def factor_scores(self, context: StrategyContext) -> dict[str, float]:
        """Rate the quality of different factors in this setup.
        
        Return a dict like: {"trend": 0.8, "volume": 0.6}
        
        Scores 0.0-1.0:
        - 0.0 = Not present / weak
        - 0.5 = Moderate
        - 1.0 = Excellent
        
        These are used by the scorer to rate the overall recommendation.
        Example: If trend=1.0 and volume=0.2, the trade might get STRONG_BUY
        if trend is weighted higher.
        
        Default: empty dict (no factor scoring).
        """
        return {}

    def explanation_text(self, context: StrategyContext) -> str:
        """Plain-English explanation for the trader.
        
        Example: "Opening range breakout in a confirmed uptrend with volume."
        
        This is shown to the trader to understand WHY the signal was generated.
        Default: strategy name.
        """
        return self.name
