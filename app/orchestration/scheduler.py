"""Market Hours Scheduler and Session Manager."""

from __future__ import annotations

from datetime import datetime, time
import time as time_module
from typing import Literal
from zoneinfo import ZoneInfo

from app.config.settings import MarketConfig
from app.logging.setup import get_logger
from app.models.time import now_ist

MarketSessionKind = Literal["pre_open", "regular", "post_market", "closed"]


class MarketSessionScheduler:
    """Calculates market trading session states in IST."""

    def __init__(self, config: MarketConfig) -> None:
        self.config = config
        self.tz = ZoneInfo(config.timezone)
        self._logger = get_logger("orchestration.scheduler")

    def get_session(self, dt: datetime | None = None) -> MarketSessionKind:
        now = (dt or now_ist()).astimezone(self.tz)
        weekday = now.weekday()

        # Check trading day (0..4 = Mon..Fri)
        if weekday not in range(5):
            return "closed"

        current_time = now.time()

        # Regular equity cash session: 09:15 to 15:30
        pre_open_start = time(9, 0)
        regular_start = time(9, 15)
        regular_end = time(15, 30)
        post_market_end = time(16, 0)

        if pre_open_start <= current_time < regular_start:
            return "pre_open"
        elif regular_start <= current_time <= regular_end:
            return "regular"
        elif regular_end < current_time <= post_market_end:
            return "post_market"
        else:
            return "closed"

    def is_market_open(self, dt: datetime | None = None) -> bool:
        return self.get_session(dt) in ("pre_open", "regular")
