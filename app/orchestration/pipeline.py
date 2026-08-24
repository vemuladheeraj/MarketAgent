"""End-to-End Market Intelligence & Options Research Pipeline.

Coordinates the complete analysis cycle:
1. Data collection & normalization
2. Data quality validation (INVALID gates signals)
3. Technical analysis & options metrics
4. Market regime classification
5. Strategy candidate evaluation
6. Signal scoring & risk assessment
7. Paper trade management & exit checking
8. Gemini contextual reasoning & contradiction detection
9. Telegram alerts & persistence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.ai.gemini.client import GeminiClient
from app.analysis.options.options_analyzer import OptionsAnalyzer
from app.analysis.regime.classifier import RegimeAssessment, RegimeClassifier
from app.analysis.technical.engine import TechnicalAnalyzer
from app.config.settings import Settings
from app.data.collectors.market_collector import MarketDataCollector
from app.data.providers.base import MarketDataProvider
from app.logging.setup import get_logger, log_event
from app.models.ai import GeminiAnalysis
from app.models.enums import DataQuality, SystemEventType
from app.models.events import SystemEvent
from app.models.options_analysis import OptionMetrics
from app.models.paper_trading import PaperPosition
from app.models.risk import RiskAssessment, RiskState
from app.models.snapshots import MarketSnapshot
from app.models.technical import TechnicalIndicators
from app.models.time import now_ist
from app.models.trading import Signal
from app.notifications.telegram.notifier import TelegramNotifier
from app.paper_trading.engine import PaperTradingEngine
from app.risk.engine import RiskEngine
from app.scoring.signal_scorer import SignalScorer
from app.storage.market_store import MarketStore
from app.strategies.base.strategy import StrategyContext
from app.strategies.engine import StrategyEngine


@dataclass
class PipelineCycleResult:
    """Summary record of one completed pipeline execution cycle."""

    timestamp: datetime
    data_quality: DataQuality
    snapshot: MarketSnapshot | None
    technicals: dict[str, TechnicalIndicators] = field(default_factory=dict)
    options: dict[str, OptionMetrics] = field(default_factory=dict)
    regimes: dict[str, RegimeAssessment] = field(default_factory=dict)
    signals: list[Signal] = field(default_factory=list)
    risk_assessments: list[RiskAssessment] = field(default_factory=list)
    opened_paper_positions: list[PaperPosition] = field(default_factory=list)
    closed_paper_positions: list[PaperPosition] = field(default_factory=list)
    gemini_analyses: dict[str, GeminiAnalysis] = field(default_factory=dict)
    alerts_dispatched: int = 0


class MarketIntelligencePipeline:
    """Orchestrates one tick/cycle across all system layers."""

    def __init__(
        self,
        *,
        settings: Settings,
        provider: MarketDataProvider,
        store: MarketStore,
        technical_analyzer: TechnicalAnalyzer | None = None,
        options_analyzer: OptionsAnalyzer | None = None,
        regime_classifier: RegimeClassifier | None = None,
        strategy_engine: StrategyEngine | None = None,
        risk_engine: RiskEngine | None = None,
        paper_engine: PaperTradingEngine | None = None,
        gemini_client: GeminiClient | None = None,
        telegram_notifier: TelegramNotifier | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.store = store
        self.technical_analyzer = technical_analyzer or TechnicalAnalyzer()
        self.options_analyzer = options_analyzer or OptionsAnalyzer()
        self.regime_classifier = regime_classifier or RegimeClassifier()
        self.strategy_engine = strategy_engine or StrategyEngine(
            signal_config=settings.signal,
            strategy_config=settings.strategies,
        )
        self.risk_engine = risk_engine
        self.paper_engine = paper_engine
        self.gemini_client = gemini_client
        self.telegram_notifier = telegram_notifier
        self.collector = MarketDataCollector(provider)
        self._logger = get_logger("orchestration.pipeline")

    def run_cycle(self) -> PipelineCycleResult:
        """Execute a single complete quantitative analysis, paper trading, and reasoning cycle."""
        t_start = now_ist()
        result = PipelineCycleResult(
            timestamp=t_start,
            data_quality=DataQuality.VALID,
            snapshot=None,
        )

        # 1. Collect market snapshot
        snapshot = self.collector.collect_snapshot(
            self.settings.market,
            self.settings.data_quality,
        )
        result.snapshot = snapshot

        # Check overall data quality from snapshot quotes
        dq_status = DataQuality.VALID
        for q in snapshot.quotes.values():
            if hasattr(q, "quality_report") and q.quality_report:
                if q.quality_report.status == DataQuality.INVALID:
                    dq_status = DataQuality.INVALID
                    break
                elif q.quality_report.status == DataQuality.WARNING:
                    dq_status = DataQuality.WARNING

        result.data_quality = dq_status

        # Persist snapshot (fail-soft)
        self.store.persist_market_snapshot(snapshot)

        # 2. Iterate watchlist symbols
        for inst in self.settings.market.instruments:
            symbol = inst.symbol

            # Fetch candles for technical analysis
            try:
                raw_candles = self.provider.get_candles(symbol, lookback_days=40, timeframe="1d")
                candles = self.collector.normalizer.normalize_candle_list(raw_candles)
            except Exception as exc:
                log_event(self._logger, "ERROR", "get_candles failed", symbol=symbol, err=str(exc))
                continue

            if not candles:
                continue

            tech = self.technical_analyzer.analyze(candles)
            result.technicals[symbol] = tech

            # Options Analysis
            chain = snapshot.option_chains.get(symbol)
            opt_metrics: OptionMetrics | None = None
            if chain:
                try:
                    opt_metrics = self.options_analyzer.analyze(chain)
                    result.options[symbol] = opt_metrics
                except Exception as exc:
                    log_event(self._logger, "ERROR", "options analysis failed", symbol=symbol, err=str(exc))

            # Market Regime Classification
            regime = self.regime_classifier.classify(
                tech,
                vix=snapshot.vix,
                breadth=snapshot.breadth,
            )
            result.regimes[symbol] = regime

            # 3. Strategy Evaluation (Gated if data is INVALID)
            if dq_status == DataQuality.INVALID:
                log_event(
                    self._logger,
                    "SIGNAL_REJECTED",
                    "signal evaluation skipped because data quality is INVALID",
                    symbol=symbol,
                )
                continue

            strat_context = StrategyContext(
                technical=tech,
                regime=regime,
                options=opt_metrics,
                breadth_score=regime.breadth_score,
            )

            signals = self.strategy_engine.evaluate(strat_context, data_quality=dq_status)
            result.signals.extend(signals)

            for sig in signals:
                self.store.persist_signal(sig)

                # 4. Risk Assessment & Paper Trading
                if sig.accepted and self.risk_engine and self.paper_engine:
                    risk_state = self.store.load_risk_state(self.settings.risk.account_size)
                    assessment = self.risk_engine.assess(sig, risk_state)
                    result.risk_assessments.append(assessment)
                    self.store.persist_risk_assessment(assessment)

                    if assessment.approved:
                        pos = self.paper_engine.open_position(sig, assessment)
                        if pos:
                            result.opened_paper_positions.append(pos)
                            if self.telegram_notifier:
                                sent = self.telegram_notifier.notify_signal(sig, assessment)
                                if sent:
                                    result.alerts_dispatched += 1

            # 5. Update open paper positions with current quote
            quote = snapshot.quotes.get(symbol)
            if quote and self.paper_engine:
                closed_positions = self.paper_engine.update_with_quote(quote)
                for c_pos in closed_positions:
                    result.closed_paper_positions.append(c_pos)
                    if self.telegram_notifier:
                        sent = self.telegram_notifier.notify_exit(c_pos)
                        if sent:
                            result.alerts_dispatched += 1

            # 6. Gemini Contextual Reasoning
            if self.gemini_client:
                news_items = None  # can be passed from NewsContextManager
                analysis = self.gemini_client.analyze_market(
                    technical=tech,
                    regime=regime,
                    options=opt_metrics,
                    breadth=snapshot.breadth,
                    signals=[s for s in signals if s.candidate.symbol == symbol],
                    news=news_items,
                )
                result.gemini_analyses[symbol] = analysis

        return result
