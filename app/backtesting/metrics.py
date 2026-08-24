"""Statistical and performance metric calculations for backtesting.

Deterministic, transparent, and tested against analytical benchmarks.
"""

from __future__ import annotations

import math
from datetime import datetime

import numpy as np

from app.models.backtesting import BacktestTrade, EquityPoint, StrategyPerformance
from app.models.time import now_ist


def calculate_performance(
    trades: list[BacktestTrade],
    *,
    initial_capital: float = 1_000_000.0,
    risk_free_rate: float = 0.06,
    periods_per_year: float = 252.0,
    start_time: datetime | None = None,
) -> tuple[StrategyPerformance, list[EquityPoint]]:
    """Compute complete performance metrics and equity curve.

    Parameters
    ----------
    trades:
        List of closed simulated trades in chronological order.
    initial_capital:
        Starting cash for the backtest in INR.
    risk_free_rate:
        Annualized risk-free rate used for Sharpe/Sortino ratios (default 6%).
    periods_per_year:
        Trading days/periods per year for annualizing ratios.
    start_time:
        Optional backtest start timestamp used if trade list is empty.
    """
    if not trades:
        t0 = start_time or now_ist()
        initial_point = EquityPoint(
            timestamp=t0,
            gross_equity=initial_capital,
            net_equity=initial_capital,
            drawdown_amount=0.0,
            drawdown_pct=0.0,
        )
        empty_metrics = StrategyPerformance(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            break_even_trades=0,
            win_rate=0.0,
            gross_pnl=0.0,
            net_pnl=0.0,
            total_costs=0.0,
            profit_factor=0.0,
            average_trade_net_pnl=0.0,
            average_win=0.0,
            average_loss=0.0,
            win_loss_ratio=0.0,
            average_r=0.0,
            expectancy=0.0,
            max_drawdown_amount=0.0,
            max_drawdown_pct=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_winning_streak=0,
            max_losing_streak=0,
            trades_by_regime={},
            pnl_by_regime={},
        )
        return empty_metrics, [initial_point]

    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t.net_pnl > 0)
    losing_trades = sum(1 for t in trades if t.net_pnl < 0)
    break_even_trades = sum(1 for t in trades if t.net_pnl == 0)
    win_rate = winning_trades / total_trades

    gross_pnl = sum(t.gross_pnl for t in trades)
    net_pnl = sum(t.net_pnl for t in trades)
    total_costs = sum(t.cost.total for t in trades)

    gross_wins = sum(t.net_pnl for t in trades if t.net_pnl > 0)
    gross_losses = abs(sum(t.net_pnl for t in trades if t.net_pnl < 0))

    if gross_losses > 0:
        profit_factor = gross_wins / gross_losses
    elif gross_wins > 0:
        profit_factor = float("inf")
    else:
        profit_factor = 0.0

    average_trade_net_pnl = net_pnl / total_trades
    average_win = (gross_wins / winning_trades) if winning_trades > 0 else 0.0
    average_loss = (gross_losses / losing_trades) if losing_trades > 0 else 0.0
    win_loss_ratio = (
        (average_win / average_loss)
        if average_loss > 0
        else (float("inf") if average_win > 0 else 0.0)
    )
    average_r = sum(t.r_multiple for t in trades) / total_trades
    expectancy = (win_rate * average_win) - ((1.0 - win_rate) * average_loss)

    # Streaks
    max_win_streak = 0
    max_lose_streak = 0
    cur_win = 0
    cur_lose = 0
    for t in trades:
        if t.net_pnl > 0:
            cur_win += 1
            cur_lose = 0
            if cur_win > max_win_streak:
                max_win_streak = cur_win
        elif t.net_pnl < 0:
            cur_lose += 1
            cur_win = 0
            if cur_lose > max_lose_streak:
                max_lose_streak = cur_lose
        else:
            cur_win = 0
            cur_lose = 0

    # Equity curve, drawdowns, and returns
    equity_curve: list[EquityPoint] = []
    current_gross = initial_capital
    current_net = initial_capital
    peak_net = initial_capital
    max_dd_amount = 0.0
    max_dd_pct = 0.0

    # Add initial point
    first_time = trades[0].entry_time
    equity_curve.append(
        EquityPoint(
            timestamp=first_time,
            gross_equity=initial_capital,
            net_equity=initial_capital,
            drawdown_amount=0.0,
            drawdown_pct=0.0,
        )
    )

    trade_returns: list[float] = []
    for t in trades:
        cap_before = current_net
        current_gross += t.gross_pnl
        current_net += t.net_pnl
        trade_ret = (t.net_pnl / cap_before) if cap_before > 0 else 0.0
        trade_returns.append(trade_ret)

        if current_net > peak_net:
            peak_net = current_net

        dd_amount = max(0.0, peak_net - current_net)
        dd_pct = (dd_amount / peak_net * 100.0) if peak_net > 0 else 0.0

        if dd_amount > max_dd_amount:
            max_dd_amount = dd_amount
        if dd_pct > max_dd_pct:
            max_dd_pct = dd_pct

        equity_curve.append(
            EquityPoint(
                timestamp=t.exit_time,
                gross_equity=current_gross,
                net_equity=current_net,
                drawdown_amount=dd_amount,
                drawdown_pct=dd_pct,
            )
        )

    # Sharpe & Sortino ratios (annualized over trade frequency)
    returns_arr = np.array(trade_returns, dtype=float)
    rf_per_trade = (1.0 + risk_free_rate) ** (1.0 / periods_per_year) - 1.0
    excess_returns = returns_arr - rf_per_trade

    mean_excess = float(np.mean(excess_returns))
    std_returns = float(np.std(returns_arr, ddof=1)) if len(returns_arr) > 1 else 0.0

    # Annualization factor based on trade sample
    annual_factor = math.sqrt(min(float(total_trades), periods_per_year))

    if std_returns > 1e-12:
        sharpe_ratio = (mean_excess / std_returns) * annual_factor
    else:
        sharpe_ratio = 0.0

    downside_diffs = np.minimum(0.0, returns_arr - rf_per_trade)
    downside_dev = (
        math.sqrt(float(np.mean(downside_diffs**2)))
        if len(downside_diffs) > 0
        else 0.0
    )

    if downside_dev > 1e-12:
        sortino_ratio = (mean_excess / downside_dev) * annual_factor
    else:
        sortino_ratio = 0.0

    # Breakdown by regime
    trades_by_regime: dict[str, int] = {}
    pnl_by_regime: dict[str, float] = {}
    for t in trades:
        r_name = t.regime.value if t.regime is not None else "unknown"
        trades_by_regime[r_name] = trades_by_regime.get(r_name, 0) + 1
        pnl_by_regime[r_name] = round(pnl_by_regime.get(r_name, 0.0) + t.net_pnl, 4)

    metrics = StrategyPerformance(
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        break_even_trades=break_even_trades,
        win_rate=round(win_rate, 4),
        gross_pnl=round(gross_pnl, 4),
        net_pnl=round(net_pnl, 4),
        total_costs=round(total_costs, 4),
        profit_factor=round(profit_factor, 4),
        average_trade_net_pnl=round(average_trade_net_pnl, 4),
        average_win=round(average_win, 4),
        average_loss=round(average_loss, 4),
        win_loss_ratio=round(win_loss_ratio, 4),
        average_r=round(average_r, 4),
        expectancy=round(expectancy, 4),
        max_drawdown_amount=round(max_dd_amount, 4),
        max_drawdown_pct=round(max_dd_pct, 4),
        sharpe_ratio=round(sharpe_ratio, 4),
        sortino_ratio=round(sortino_ratio, 4),
        max_winning_streak=max_win_streak,
        max_losing_streak=max_lose_streak,
        trades_by_regime=trades_by_regime,
        pnl_by_regime=pnl_by_regime,
    )
    return metrics, equity_curve
