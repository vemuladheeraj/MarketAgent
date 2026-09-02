"""Market Hours Scheduler and Session Manager.

Supports both Indian (NSE/NIFTY) and US (NYSE/NASDAQ/OPRA) market hours.
Can run on Indian hours, US hours, or both (24/5).
"""

from __future__ import annotations

from datetime import datetime, time
import time as time_module
from typing import Literal
from zoneinfo import ZoneInfo

from app.config.settings import MarketConfig
from app.logging.setup import get_logger
from app.models.time import now_ist

MarketSessionKind = Literal["pre_open", "regular", "post_market", "closed"]
TradingMarket = Literal["india", "us", "both"]


class MarketSessionScheduler:
    """Calculates market trading session states.
    
    Supports:
    - India (IST timezone): 09:15-15:30 Mon-Fri
    - US (EST/EDT timezone): 09:30-16:00 Mon-Fri
    - Both: 24/5 continuous trading
    """

    def __init__(self, config: MarketConfig) -> None:
        self.config = config
        self.tz = ZoneInfo(config.timezone)
        self._logger = get_logger("orchestration.scheduler")
        
        # Market configuration
        self.active_markets: TradingMarket = getattr(config, "active_markets", "india")  # "india", "us", or "both"
        self.us_timezone = ZoneInfo("America/New_York")  # EST/EDT

    def get_session(self, dt: datetime | None = None, market: str = "india") -> MarketSessionKind:
        """Get session state for specified market.
        
        Parameters
        ----------
        dt:
            DateTime to check (default: now in IST)
        market:
            "india" (default) or "us"
        """
        if market.lower() == "us":
            return self._get_us_session(dt or now_ist())
        else:
            return self._get_india_session(dt or now_ist())

    def _get_india_session(self, dt: datetime) -> MarketSessionKind:
        """Get NSE India trading session state (IST timezone)."""
        now = dt.astimezone(self.tz)
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

    def _get_us_session(self, dt: datetime) -> MarketSessionKind:
        """Get NYSE/NASDAQ trading session state (US Eastern timezone).
        
        US Equity Markets (stock options):
        - Pre-market: 04:00 - 09:30 EST
        - Regular: 09:30 - 16:00 EST
        - After-hours: 16:00 - 20:00 EST
        
        US Options (OPRA):
        - Closes at 16:15 EST (15 min after stock market)
        """
        now = dt.astimezone(self.us_timezone)
        weekday = now.weekday()

        # Check trading day (0..4 = Mon..Fri)
        if weekday not in range(5):
            return "closed"

        current_time = now.time()

        # US equity market hours (ET)
        pre_open_start = time(4, 0)
        regular_start = time(9, 30)
        regular_end = time(16, 0)
        post_market_end = time(20, 0)  # Extended hours until 8 PM ET

        if pre_open_start <= current_time < regular_start:
            return "pre_open"
        elif regular_start <= current_time <= regular_end:
            return "regular"
        elif regular_end < current_time <= post_market_end:
            return "post_market"
        else:
            return "closed"

    def is_market_open(self, dt: datetime | None = None, market: str = "india") -> bool:
        """Check if specified market is currently open for trading."""
        return self.get_session(dt, market) in ("pre_open", "regular")

    def is_any_market_open(self, dt: datetime | None = None) -> bool:
        """Check if ANY configured market is currently open."""
        if self.active_markets == "both":
            return self.is_market_open(dt, "india") or self.is_market_open(dt, "us")
        elif self.active_markets == "us":
            return self.is_market_open(dt, "us")
        else:  # india
            return self.is_market_open(dt, "india")

    def get_active_markets(self) -> list[str]:
        """Get list of currently active markets."""
        if self.active_markets == "both":
            markets = []
            if self.is_market_open(market="india"):
                markets.append("india")
            if self.is_market_open(market="us"):
                markets.append("us")
            return markets
        elif self.active_markets == "us":
            return ["us"] if self.is_market_open(market="us") else []
        else:  # india
            return ["india"] if self.is_market_open(market="india") else []

    def next_market_open(self, dt: datetime | None = None) -> tuple[datetime, str]:
        """Calculate next market open time and which market.
        
        Returns:
            (next_open_datetime, market_name)
        """
        now = dt or now_ist()
        
        # Check both markets
        india_open = self._next_india_open(now)
        us_open = self._next_us_open(now)
        
        if india_open < us_open:
            return (india_open, "india")
        else:
            return (us_open, "us")

    def _next_india_open(self, dt: datetime) -> datetime:
        """Next NSE India market open time."""
        dt_ist = dt.astimezone(self.tz)
        current_time = dt_ist.time()
        
        # If before 09:15 today, return today 09:15
        if current_time < time(9, 15):
            return dt_ist.replace(hour=9, minute=15, second=0, microsecond=0)
        
        # Otherwise, find next weekday at 09:15
        next_day = dt_ist.replace(hour=9, minute=15, second=0, microsecond=0)
        next_day += time_module.__import__('datetime').timedelta(days=1)
        
        # Skip weekends
        while next_day.weekday() > 4:
            next_day += time_module.__import__('datetime').timedelta(days=1)
        
        return next_day

    def _next_us_open(self, dt: datetime) -> datetime:
        """Next NYSE/NASDAQ market open time."""
        dt_et = dt.astimezone(self.us_timezone)
        current_time = dt_et.time()
        
        # If before 09:30 today, return today 09:30
        if current_time < time(9, 30):
            return dt_et.replace(hour=9, minute=30, second=0, microsecond=0)
        
        # Otherwise, find next weekday at 09:30
        next_day = dt_et.replace(hour=9, minute=30, second=0, microsecond=0)
        next_day += time_module.__import__('datetime').timedelta(days=1)
        
        # Skip weekends
        while next_day.weekday() > 4:
            next_day += time_module.__import__('datetime').timedelta(days=1)
        
        return next_day

    def get_market_hours_info(self) -> dict[str, str]:
        """Get human-readable market hours information."""
        return {
            "india_nse": "09:15 - 15:30 IST, Monday-Friday",
            "us_nyse_nasdaq": "09:30 - 16:00 ET (EST/EDT), Monday-Friday",
            "us_premarket": "04:00 - 09:30 ET",
            "us_after_hours": "16:00 - 20:00 ET",
            "active_markets": self.active_markets,
        }

