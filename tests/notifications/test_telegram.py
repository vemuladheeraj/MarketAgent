"""Unit tests for Telegram bot commands, formatters, and alert notifier."""

from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from app.config.settings import FirestoreConfig, TelegramConfig, TransactionCostConfig
from app.models.backtesting import ExitReason
from app.models.candle import MarketQuote
from app.models.enums import DataQuality, Direction, SignalClassification, TradeStage
from app.models.options_analysis import OISummary, OptionMetrics
from app.models.paper_trading import PaperPosition
from app.models.risk import CostBreakdown, PositionSize, RiskAssessment
from app.models.snapshots import MarketSnapshot
from app.models.time import IST
from app.models.trading import Signal, StrategyCandidate
from app.notifications.telegram.bot import TelegramCommandHandler
from app.notifications.telegram.client import TelegramClient
from app.notifications.telegram.notifier import TelegramNotifier
from app.paper_trading.engine import PaperTradingEngine
from app.risk.costs import TransactionCostModel
from app.storage.market_store import MarketStore

TS = datetime(2025, 6, 27, 9, 15, tzinfo=IST)

ZERO_COSTS = TransactionCostConfig(
    brokerage=0.0,
    stt_buy_pct=0.0,
    stt_sell_pct=0.0,
    gst_pct=0.0,
    exchange_charges_pct=0.0,
    sebi_charges_pct=0.0,
    stamp_duty_pct=0.0,
    slippage_pct=0.0,
    bid_ask_spread_pct=0.0,
)


def _sample_signal(accepted: bool = True) -> tuple[Signal, RiskAssessment]:
    cand = StrategyCandidate(
        strategy_name="opening_range_breakout",
        symbol="NIFTY",
        timestamp=TS,
        direction=Direction.LONG,
        entry=20000.0,
        stop_loss=19950.0,
        targets=[20100.0],
        explanation="ORB setup in uptrend",
    )
    sig = Signal(
        candidate=cand,
        score=82.0,
        classification=SignalClassification.HIGH_QUALITY,
        accepted=accepted,
        timestamp=TS,
    )
    pos_size = PositionSize(
        quantity=2,
        lot_size=50,
        point_value=1.0,
        risk_budget=10000.0,
        risk_per_unit=50.0,
        estimated_stop_loss=5000.0,
        account_size=1_000_000.0,
        risk_per_trade_pct=1.0,
    )
    cost = CostBreakdown(
        notional_entry=2000000.0,
        notional_exit=2010000.0,
        brokerage=40.0,
        stt=25.0,
        gst=10.0,
        exchange_charges=5.0,
        sebi_charges=0.1,
        stamp_duty=3.0,
        slippage=10.0,
        spread=6.9,
        total=100.0,
    )
    risk = RiskAssessment(
        approved=accepted,
        timestamp=TS,
        symbol="NIFTY",
        strategy_name="opening_range_breakout",
        position_size=pos_size,
        round_trip_cost=cost,
    )
    return sig, risk


class TestTelegramNotifier:
    def test_market_open_and_signal_alerts(self):
        client = TelegramClient(TelegramConfig(bot_token="", chat_id="12345"))
        notifier = TelegramNotifier(client)

        # Market open alert
        ok_open = notifier.notify_market_open(
            symbol="NIFTY",
            regime="UPTREND",
            vix=13.5,
            levels={"R1": 20100.0, "S1": 19900.0},
        )
        assert ok_open
        assert len(client.sent_messages) == 1
        assert "Market Opening Context" in client.sent_messages[0]["text"]
        assert "UPTREND" in client.sent_messages[0]["text"]

        # Signal alert
        sig, risk = _sample_signal(accepted=True)
        ok_sig = notifier.notify_signal(sig, risk)
        assert ok_sig
        assert len(client.sent_messages) == 2
        assert "Signal Alert: NIFTY" in client.sent_messages[1]["text"]

        # Unaccepted signal does not send
        unaccepted, _ = _sample_signal(accepted=False)
        ok_rej = notifier.notify_signal(unaccepted)
        assert not ok_rej
        assert len(client.sent_messages) == 2

    def test_exit_and_daily_report_alerts(self):
        client = TelegramClient(TelegramConfig(bot_token="", chat_id="12345"))
        notifier = TelegramNotifier(client)

        pos = PaperPosition(
            position_id="pos_1",
            strategy_name="orb",
            symbol="NIFTY",
            direction=Direction.LONG,
            stage=TradeStage.RESULT,
            planned_entry=20000.0,
            simulated_entry=20000.0,
            entry_time=TS,
            quantity=1,
            lot_size=50,
            point_value=1.0,
            stop_loss=19950.0,
            targets=[20100.0],
            current_price=20100.0,
            open_time=TS,
            last_update_time=TS + timedelta(minutes=15),
            exit_time=TS + timedelta(minutes=15),
            exit_price=20100.0,
            exit_reason=ExitReason.TARGET,
            gross_pnl=5000.0,
            net_pnl=4900.0,
            r_multiple=2.0,
        )

        notifier.notify_exit(pos)
        assert len(client.sent_messages) == 1
        assert "Paper Position Closed (🎉 PROFIT)" in client.sent_messages[0]["text"]

        notifier.notify_daily_report(
            date_str="27-Jun-2025",
            total_signals=4,
            paper_trades_count=2,
            wins=2,
            losses=0,
            net_pnl=9800.0,
            total_costs=200.0,
            regime="UPTREND",
        )
        assert len(client.sent_messages) == 2
        assert "End-of-Day Market Report" in client.sent_messages[1]["text"]


class TestTelegramCommandHandler:
    def test_commands_dispatch(self):
        store = MarketStore(FirestoreConfig(project_id=""))
        cost_model = TransactionCostModel(ZERO_COSTS)
        paper_engine = PaperTradingEngine(store, cost_model)
        handler = TelegramCommandHandler(store, paper_engine)

        # /status
        resp_status = handler.handle_command("/status")
        assert "Indian Market Research Agent — Status" in resp_status

        # /signals
        resp_sigs = handler.handle_command("/signals")
        assert "Signals" in resp_sigs

        # /vix
        resp_vix = handler.handle_command("/vix")
        assert "India VIX" in resp_vix

        # /watchlist
        resp_wl = handler.handle_command("/watchlist")
        assert "NIFTY" in resp_wl

        # /papertrades
        resp_pt = handler.handle_command("/papertrades")
        assert "Paper Trading Summary" in resp_pt

        # /performance
        resp_perf = handler.handle_command("/performance")
        assert "Paper Strategy Performance" in resp_perf

        # unknown
        resp_unknown = handler.handle_command("/unknown")
        assert "Available commands" in resp_unknown
