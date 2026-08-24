"""Unit tests for backtest performance and statistical metrics."""

from __future__ import annotations

from datetime import datetime, timedelta
import pytest

from app.models.backtesting import BacktestTrade, ExitReason
from app.models.enums import Direction, MarketRegime
from app.models.risk import CostBreakdown
from app.models.time import IST
from app.backtesting.metrics import calculate_performance

TS = datetime(2025, 6, 27, 9, 15, tzinfo=IST)


def _make_trade(
    trade_id: str,
    *,
    net_pnl: float,
    gross_pnl: float | None = None,
    cost_total: float = 100.0,
    r_multiple: float = 1.0,
    regime: MarketRegime = MarketRegime.UPTREND,
    bars_held: int = 5,
    offset_minutes: int = 0,
) -> BacktestTrade:
    entry_time = TS + timedelta(minutes=offset_minutes)
    exit_time = entry_time + timedelta(minutes=bars_held * 5)
    g_pnl = gross_pnl if gross_pnl is not None else (net_pnl + cost_total)
    cost = CostBreakdown(
        notional_entry=10000.0,
        notional_exit=10000.0,
        brokerage=40.0,
        stt=25.0,
        gst=10.0,
        exchange_charges=5.0,
        sebi_charges=0.1,
        stamp_duty=3.0,
        slippage=10.0,
        spread=6.9,
        total=cost_total,
        formula="test_cost",
    )
    return BacktestTrade(
        trade_id=trade_id,
        strategy_name="test_strat",
        symbol="NIFTY",
        direction=Direction.LONG,
        entry_time=entry_time,
        exit_time=exit_time,
        entry_price=20000.0,
        exit_price=20100.0,
        quantity=1,
        lot_size=50,
        point_value=1.0,
        stop_loss=19900.0,
        target_price=20200.0,
        exit_reason=ExitReason.TARGET if net_pnl > 0 else ExitReason.STOP_LOSS,
        gross_pnl=g_pnl,
        net_pnl=net_pnl,
        cost=cost,
        r_multiple=r_multiple,
        holding_period_bars=bars_held,
        regime=regime,
        mae=10.0,
        mfe=50.0,
    )


class TestBacktestMetrics:
    def test_empty_trades_produces_clean_defaults(self):
        metrics, equity_curve = calculate_performance([], initial_capital=500_000.0, start_time=TS)
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0
        assert metrics.profit_factor == 0.0
        assert metrics.net_pnl == 0.0
        assert metrics.gross_pnl == 0.0
        assert metrics.max_drawdown_amount == 0.0
        assert metrics.max_drawdown_pct == 0.0
        assert len(equity_curve) == 1
        assert equity_curve[0].net_equity == 500_000.0

    def test_exact_win_rate_and_profit_factor(self):
        # 3 wins: +2000, +3000, +1000 (total gains = 6000)
        # 2 losses: -1500, -500 (total losses = 2000)
        trades = [
            _make_trade("t1", net_pnl=2000.0, r_multiple=2.0, offset_minutes=10),
            _make_trade("t2", net_pnl=-1500.0, r_multiple=-1.5, offset_minutes=20),
            _make_trade("t3", net_pnl=3000.0, r_multiple=3.0, offset_minutes=30),
            _make_trade("t4", net_pnl=-500.0, r_multiple=-0.5, offset_minutes=40),
            _make_trade("t5", net_pnl=1000.0, r_multiple=1.0, offset_minutes=50),
        ]
        metrics, equity_curve = calculate_performance(trades, initial_capital=100_000.0)

        assert metrics.total_trades == 5
        assert metrics.winning_trades == 3
        assert metrics.losing_trades == 2
        assert metrics.break_even_trades == 0
        assert metrics.win_rate == 0.6  # 3/5
        assert metrics.net_pnl == 4000.0  # 6000 - 2000
        assert metrics.profit_factor == 3.0  # 6000 / 2000
        assert metrics.average_win == 2000.0  # 6000 / 3
        assert metrics.average_loss == 1000.0  # 2000 / 2
        assert metrics.win_loss_ratio == 2.0  # 2000 / 1000
        assert metrics.average_trade_net_pnl == 800.0  # 4000 / 5
        assert metrics.average_r == 0.8  # (2 - 1.5 + 3 - 0.5 + 1) / 5 = 4 / 5

        # Expectancy: (0.6 * 2000) - (0.4 * 1000) = 1200 - 400 = 800
        assert abs(metrics.expectancy - 800.0) < 1e-6

    def test_streaks_calculation(self):
        # Sequence: Win, Win, Win, Loss, Loss, Win, Loss
        # Max win streak = 3, Max loss streak = 2
        trades = [
            _make_trade("t1", net_pnl=100.0, offset_minutes=10),
            _make_trade("t2", net_pnl=100.0, offset_minutes=20),
            _make_trade("t3", net_pnl=100.0, offset_minutes=30),
            _make_trade("t4", net_pnl=-50.0, offset_minutes=40),
            _make_trade("t5", net_pnl=-50.0, offset_minutes=50),
            _make_trade("t6", net_pnl=100.0, offset_minutes=60),
            _make_trade("t7", net_pnl=-50.0, offset_minutes=70),
        ]
        metrics, _ = calculate_performance(trades)
        assert metrics.max_winning_streak == 3
        assert metrics.max_losing_streak == 2

    def test_drawdown_calculation(self):
        # Initial = 100,000
        # t1: +10,000 -> 110,000 (peak = 110,000)
        # t2: -11,000 -> 99,000 (DD = 11,000, DD% = 11,000 / 110,000 = 10%)
        # t3: +5,000 -> 104,000 (DD = 6,000)
        # t4: +8,000 -> 112,000 (peak = 112,000, DD = 0)
        # t5: -22,400 -> 89,600 (DD = 22,400, DD% = 22,400 / 112,000 = 20%)
        trades = [
            _make_trade("t1", net_pnl=10_000.0, offset_minutes=10),
            _make_trade("t2", net_pnl=-11_000.0, offset_minutes=20),
            _make_trade("t3", net_pnl=5_000.0, offset_minutes=30),
            _make_trade("t4", net_pnl=8_000.0, offset_minutes=40),
            _make_trade("t5", net_pnl=-22_400.0, offset_minutes=50),
        ]
        metrics, equity_curve = calculate_performance(trades, initial_capital=100_000.0)
        assert metrics.max_drawdown_amount == 22_400.0
        assert abs(metrics.max_drawdown_pct - 20.0) < 1e-4

        # Verify equity points match
        assert len(equity_curve) == 6  # initial + 5 trades
        assert equity_curve[-1].net_equity == 89_600.0
        assert abs(equity_curve[-1].drawdown_pct - 20.0) < 1e-4

    def test_all_wins_and_all_losses(self):
        # All wins
        wins = [
            _make_trade("t1", net_pnl=1000.0, offset_minutes=10),
            _make_trade("t2", net_pnl=2000.0, offset_minutes=20),
        ]
        m_win, _ = calculate_performance(wins)
        assert m_win.win_rate == 1.0
        assert m_win.profit_factor == float("inf")
        assert m_win.average_loss == 0.0
        assert m_win.max_losing_streak == 0
        assert m_win.max_winning_streak == 2

        # All losses
        losses = [
            _make_trade("t1", net_pnl=-500.0, offset_minutes=10),
            _make_trade("t2", net_pnl=-300.0, offset_minutes=20),
        ]
        m_loss, _ = calculate_performance(losses)
        assert m_loss.win_rate == 0.0
        assert m_loss.profit_factor == 0.0
        assert m_loss.average_win == 0.0
        assert m_loss.max_winning_streak == 0
        assert m_loss.max_losing_streak == 2

    def test_regime_attribution(self):
        trades = [
            _make_trade("t1", net_pnl=1000.0, regime=MarketRegime.STRONG_UPTREND, offset_minutes=10),
            _make_trade("t2", net_pnl=500.0, regime=MarketRegime.STRONG_UPTREND, offset_minutes=20),
            _make_trade("t3", net_pnl=-800.0, regime=MarketRegime.RANGE, offset_minutes=30),
        ]
        metrics, _ = calculate_performance(trades)
        assert metrics.trades_by_regime["strong_uptrend"] == 2
        assert metrics.trades_by_regime["range"] == 1
        assert metrics.pnl_by_regime["strong_uptrend"] == 1500.0
        assert metrics.pnl_by_regime["range"] == -800.0
