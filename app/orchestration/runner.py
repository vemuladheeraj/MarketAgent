"""Application runner and lifecycle coordinator.

The runner owns the application lifecycle:
1. Load & validate configuration
2. Configure logging
3. Initialize MarketStore & Data Provider
4. Initialize Risk, Paper Trading, Gemini, Telegram
5. Wire MarketIntelligencePipeline
6. Run single-cycle or daemon scheduler
7. Graceful shutdown
"""

from __future__ import annotations

import logging
import signal
import threading
import time
from dataclasses import dataclass, field
from types import FrameType

from app import __version__
from app.ai.gemini.client import GeminiClient
from app.config.settings import Settings
from app.data.collectors.market_collector import MarketDataCollector
from app.data.providers.base import MarketDataProvider, ProviderError
from app.data.providers.factory import create_provider
from app.logging.setup import configure_logging, get_logger, log_event
from app.models.enums import SystemEventType
from app.models.events import SystemEvent
from app.models.snapshots import MarketSnapshot
from app.models.time import now_ist
from app.notifications.telegram.bot import TelegramCommandHandler
from app.notifications.telegram.client import TelegramClient
from app.notifications.telegram.notifier import TelegramNotifier
from app.orchestration.pipeline import MarketIntelligencePipeline, PipelineCycleResult
from app.orchestration.scheduler import MarketSessionScheduler
from app.paper_trading.engine import PaperTradingEngine
from app.paper_trading.tracker import PaperPerformanceTracker
from app.risk.costs import TransactionCostModel
from app.risk.engine import RiskEngine
from app.storage.market_store import MarketStore


@dataclass
class AppContext:
    """Complete runtime context of all active system subsystems."""

    settings: Settings
    store: MarketStore
    provider: MarketDataProvider | None = None
    cost_model: TransactionCostModel = field(init=False)
    risk_engine: RiskEngine = field(init=False)
    paper_engine: PaperTradingEngine = field(init=False)
    paper_tracker: PaperPerformanceTracker = field(init=False)
    gemini_client: GeminiClient = field(init=False)
    telegram_client: TelegramClient = field(init=False)
    telegram_notifier: TelegramNotifier = field(init=False)
    command_handler: TelegramCommandHandler = field(init=False)
    scheduler: MarketSessionScheduler = field(init=False)
    pipeline: MarketIntelligencePipeline | None = None
    logger: logging.Logger = field(init=False)

    def __post_init__(self) -> None:
        self.logger = get_logger("orchestration")
        self.cost_model = TransactionCostModel(self.settings.transaction_costs)
        self.risk_engine = RiskEngine(
            self.settings.risk,
            self.cost_model,
        )
        self.paper_engine = PaperTradingEngine(
            self.store,
            self.cost_model,
            default_account_size=self.settings.risk.account_size,
        )
        self.paper_tracker = PaperPerformanceTracker(
            initial_capital=self.settings.risk.account_size,
        )
        self.gemini_client = GeminiClient(self.settings.gemini)
        self.telegram_client = TelegramClient(self.settings.telegram)
        self.telegram_notifier = TelegramNotifier(self.telegram_client)
        self.command_handler = TelegramCommandHandler(
            self.store,
            self.paper_engine,
            self.paper_tracker,
        )
        self.scheduler = MarketSessionScheduler(self.settings.market)

        if self.provider is not None:
            self.pipeline = MarketIntelligencePipeline(
                settings=self.settings,
                provider=self.provider,
                store=self.store,
                risk_engine=self.risk_engine,
                paper_engine=self.paper_engine,
                gemini_client=self.gemini_client,
                telegram_notifier=self.telegram_notifier,
            )


class MarketAgentApplication:
    """Full lifecycle manager for the quantitative research agent."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._started = False
        self._shutdown_requested = False
        self._logger = logging.getLogger("market")

    def startup(self) -> AppContext:
        configure_logging(self.settings.logging)
        self._logger = get_logger("orchestration")
        store = MarketStore(self.settings.firestore)
        provider: MarketDataProvider | None = None
        try:
            provider = create_provider(self.settings.provider)
        except ProviderError as exc:
            log_event(
                self._logger,
                "ERROR",
                "data provider not initialised",
                err=str(exc),
            )

        context = AppContext(
            settings=self.settings,
            store=store,
            provider=provider,
        )
        context.logger.info(
            "EVENT=APP_START MSG=application starting environment=%s version=%s storage=%s",
            self.settings.environment,
            __version__,
            store.backend,
        )
        context.logger.info("CONFIG_SUMMARY %s", self._config_summary())
        context.store.persist_system_event(
            SystemEvent(
                event_type=SystemEventType.APP_START,
                timestamp=now_ist(),
                message="application starting",
                source="orchestration",
                details={"storage": store.backend, "version": __version__},
            )
        )
        self._started = True
        return context

    def collect_and_persist(self, context: AppContext) -> MarketSnapshot | None:
        """Collect one snapshot and persist it (convenience helper)."""
        if context.provider is None:
            log_event(context.logger, "ERROR", "collect skipped; no provider")
            return None
        collector = MarketDataCollector(context.provider, logger=get_logger("data.collector"))
        snapshot = collector.collect_snapshot(
            self.settings.market,
            self.settings.data_quality,
        )
        context.store.persist_market_snapshot(snapshot)
        return snapshot

    def run_cycle(self, context: AppContext) -> PipelineCycleResult | None:
        """Run one complete pipeline cycle."""
        if context.pipeline is None:
            log_event(context.logger, "ERROR", "cannot run cycle: pipeline not initialized")
            return None
        return context.pipeline.run_cycle()

    def run_daemon(self, context: AppContext, *, interval_seconds: float = 60.0, max_cycles: int | None = None) -> None:
        """Run continuous market monitoring loop with scheduler awareness."""
        self._setup_signals()
        cycles = 0
        context.logger.info("DAEMON_STARTED interval=%.1fs", interval_seconds)

        while not self._shutdown_requested:
            is_open = context.scheduler.is_market_open()
            session = context.scheduler.get_session()
            log_event(context.logger, "DEBUG", "scheduler tick", session=session, is_open=is_open)

            if is_open:
                try:
                    self.run_cycle(context)
                except Exception as exc:  # noqa: BLE001
                    log_event(context.logger, "ERROR", "pipeline cycle error", err=str(exc))

            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                break

            time.sleep(interval_seconds)

    def shutdown(self) -> None:
        if self._started:
            self._logger.info("EVENT=APP_STOP MSG=application shutdown complete")
            self._started = False

    def is_started(self) -> bool:
        return self._started

    def _setup_signals(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return

        def _handler(sig: int, frame: FrameType | None) -> None:
            self._logger.info("Shutdown signal received: %d", sig)
            self._shutdown_requested = True

        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)

    def _config_summary(self) -> str:
        instruments = ", ".join(i.symbol for i in self.settings.market.instruments)
        sessions = ", ".join(self.settings.market.sessions)
        return (
            f"timezone={self.settings.timezone} sessions=[{sessions}] "
            f"instruments=[{instruments}] provider={self.settings.provider.name} "
            f"risk={self.settings.risk.risk_per_trade_pct}%/trade "
            f"signal_min={self.settings.signal.min_signal_score}"
        )
