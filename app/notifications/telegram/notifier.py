"""Telegram Alert Dispatcher."""

from __future__ import annotations

from app.logging.setup import get_logger
from app.models.backtesting import StrategyPerformance
from app.models.options_analysis import OptionMetrics
from app.models.paper_trading import PaperPosition
from app.models.risk import RiskAssessment
from app.models.trading import Signal
from app.notifications.telegram.client import TelegramClient
from app.notifications.telegram.formatters import (
    format_daily_report,
    format_exit_alert,
    format_market_open_alert,
    format_options_summary,
    format_signal_alert,
)


class TelegramNotifier:
    """Dispatches proactive formatted alerts via TelegramClient."""

    def __init__(self, client: TelegramClient) -> None:
        self.client = client
        self._logger = get_logger("notifications.telegram.notifier")

    def notify_market_open(
        self,
        *,
        symbol: str = "NIFTY",
        regime: str = "UPTREND",
        vix: float | None = None,
        levels: dict[str, float] | None = None,
        watchlist: list[str] | None = None,
    ) -> bool:
        text = format_market_open_alert(
            symbol=symbol,
            regime=regime,
            vix=vix,
            levels=levels,
            watchlist=watchlist,
        )
        return self.client.send_message(text)

    def notify_signal(self, signal: Signal, risk: RiskAssessment | None = None) -> bool:
        if not signal.accepted:
            return False
        text = format_signal_alert(signal, risk)
        return self.client.send_message(text)

    def notify_exit(self, position: PaperPosition) -> bool:
        text = format_exit_alert(position)
        return self.client.send_message(text)

    def notify_daily_report(
        self,
        *,
        date_str: str,
        total_signals: int,
        paper_trades_count: int,
        wins: int,
        losses: int,
        net_pnl: float,
        total_costs: float,
        regime: str,
        performance: StrategyPerformance | None = None,
    ) -> bool:
        text = format_daily_report(
            date_str=date_str,
            total_signals=total_signals,
            paper_trades_count=paper_trades_count,
            wins=wins,
            losses=losses,
            net_pnl=net_pnl,
            total_costs=total_costs,
            regime=regime,
            performance=performance,
        )
        return self.client.send_message(text)

    def notify_options_summary(self, metrics: OptionMetrics) -> bool:
        text = format_options_summary(metrics)
        return self.client.send_message(text)

    def notify_trade_brief(self, brief: TradeBrief) -> bool:
        """Push a present-moment trade brief (actionable or WAIT)."""
        text = format_trade_brief(brief)
        return self.client.send_message(text)
