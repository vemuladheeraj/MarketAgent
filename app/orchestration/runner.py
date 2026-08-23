"""Basic application runner.

The runner owns the application lifecycle:

    load config -> validate -> configure logging -> startup -> shutdown

Later phases extend startup() with data provider, Firestore, Telegram and
Gemini initialisation inside this same lifecycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app import __version__
from app.config.settings import Settings
from app.logging.setup import configure_logging, get_logger


@dataclass
class AppContext:
    """Everything a component needs after startup."""

    settings: Settings
    logger: logging.Logger = field(init=False)

    def __post_init__(self) -> None:
        self.logger = get_logger("orchestration")


class MarketAgentApplication:
    """Lifecycle manager for the research agent."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._started = False
        self._logger = logging.getLogger("market")  # replaced in startup

    # -- lifecycle -----------------------------------------------------
    def startup(self) -> AppContext:
        configure_logging(self.settings.logging)
        self._logger = get_logger("orchestration")
        context = AppContext(settings=self.settings)

        context.logger.info(
            "EVENT=APP_START MSG=application starting environment=%s version=%s",
            self.settings.environment,
            __version__,
        )
        context.logger.info("CONFIG_SUMMARY %s", self._config_summary())
        self._started = True
        return context

    def shutdown(self) -> None:
        if self._started:
            self._logger.info("EVENT=APP_STOP MSG=application shutdown complete")
            self._started = False

    def is_started(self) -> bool:
        return self._started

    # --------------------------------------------------------------
    def _config_summary(self) -> str:
        """Human-readable non-secret configuration summary."""
        instruments = ", ".join(i.symbol for i in self.settings.market.instruments)
        sessions = ", ".join(self.settings.market.sessions)
        return (
            f"timezone={self.settings.timezone} sessions=[{sessions}] "
            f"instruments=[{instruments}] provider={self.settings.provider.name} "
            f"risk={self.settings.risk.risk_per_trade_pct}%/trade "
            f"signal_min={self.settings.signal.min_signal_score}"
        )