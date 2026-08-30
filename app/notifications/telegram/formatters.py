"""Telegram message and alert formatters.

Produces human-readable Markdown messages for alerts, daily reports,
and bot command responses.
"""

from __future__ import annotations

from typing import Any

from app.models.backtesting import StrategyPerformance
from app.models.advisor import TradeBrief
from app.models.enums import Direction
from app.models.options_analysis import OptionMetrics
from app.models.paper_trading import PaperPosition
from app.models.risk import RiskAssessment
from app.models.snapshots import MarketSnapshot
from app.models.trading import Signal


def format_market_open_alert(
    *,
    symbol: str = "NIFTY",
    regime: str = "UPTREND",
    vix: float | None = None,
    levels: dict[str, float] | None = None,
    watchlist: list[str] | None = None,
) -> str:
    vix_str = f"{vix:.2f}" if vix is not None else "N/A"
    levels_str = ""
    if levels:
        levels_str = "\n".join(f"• {k}: {v:.1f}" for k, v in levels.items())
    else:
        levels_str = "• Levels: Neutral"

    wl_str = ", ".join(watchlist or [symbol])

    return (
        f"🌅 *Market Opening Context ({symbol})*\n\n"
        f"• *Regime*: `{regime}`\n"
        f"• *India VIX*: `{vix_str}`\n"
        f"• *Watchlist*: `{wl_str}`\n\n"
        f"*Key Structural Levels:*\n"
        f"{levels_str}\n\n"
        f"⚠️ _Personal quantitative research artifact. No real trades._"
    )


def format_signal_alert(signal: Signal, risk: RiskAssessment | None = None) -> str:
    cand = signal.candidate
    direction_emoji = "🟢 LONG" if cand.direction == Direction.LONG else "🔴 SHORT"
    pos_size = risk.position_size if risk else None
    qty_str = f"{pos_size.quantity} lots ({pos_size.units} units)" if pos_size else "1 lot"
    cost_str = f"₹{risk.round_trip_cost.total:.2f}" if risk and risk.round_trip_cost else "est. ₹150"

    targets_str = ", ".join(f"{t:.1f}" for t in cand.targets)

    return (
        f"⚡ *Signal Alert: {cand.symbol}* ({direction_emoji})\n\n"
        f"• *Strategy*: `{cand.strategy_name}`\n"
        f"• *Score*: `{signal.score:.1f}` ({signal.classification.value.upper()})\n"
        f"• *Entry*: `{cand.entry:.1f}`\n"
        f"• *Stop Loss*: `{cand.stop_loss:.1f}`\n"
        f"• *Targets*: `{targets_str}`\n"
        f"• *Position Size*: `{qty_str}`\n"
        f"• *Est. Round-Trip Cost*: `{cost_str}`\n\n"
        f"📝 *Rationale*: {cand.explanation}\n"
        f"⚠️ _Paper trading signal. Strictly educational._"
    )


def format_exit_alert(position: PaperPosition) -> str:
    pnl = position.net_pnl or 0.0
    pnl_emoji = "🎉 PROFIT" if pnl > 0 else "🛑 LOSS"
    reason = position.exit_reason.value.upper() if position.exit_reason else "CLOSED"

    return (
        f"🏁 *Paper Position Closed ({pnl_emoji})*\n\n"
        f"• *Symbol*: `{position.symbol}` ({position.direction.value.upper()})\n"
        f"• *Strategy*: `{position.strategy_name}`\n"
        f"• *Exit Reason*: `{reason}`\n"
        f"• *Entry*: `{position.simulated_entry:.1f}` → *Exit*: `{position.exit_price or 0.0:.1f}`\n"
        f"• *Gross P&L*: ₹{position.gross_pnl or 0.0:.2f}\n"
        f"• *Costs*: ₹{position.cost.total if position.cost else 0.0:.2f}\n"
        f"• *Net P&L*: *₹{pnl:.2f}*\n"
        f"• *R-Multiple*: `{position.r_multiple or 0.0:.2f}R`\n"
        f"• *MAE / MFE*: `{position.mae:.1f} pts / {position.mfe:.1f} pts`"
    )


def format_daily_report(
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
) -> str:
    win_rate = (wins / paper_trades_count * 100) if paper_trades_count > 0 else 0.0

    return (
        f"📊 *End-of-Day Market Report ({date_str})*\n\n"
        f"• *Market Regime*: `{regime}`\n"
        f"• *Signals Evaluated*: `{total_signals}`\n"
        f"• *Paper Trades Executed*: `{paper_trades_count}`\n"
        f"• *Win / Loss*: `{wins} W / {losses} L` ({win_rate:.1f}% win rate)\n"
        f"• *Net Realized P&L*: *₹{net_pnl:.2f}*\n"
        f"• *Total Transaction Costs*: ₹{total_costs:.2f}\n"
        f"• *Profit Factor*: `{performance.profit_factor if performance else 0.0:.2f}`\n\n"
        f"🔒 _Research mode: No live capital was placed._"
    )


def format_options_summary(metrics: OptionMetrics) -> str:
    pcr_str = f"{metrics.oi.pcr:.2f}" if metrics.oi.pcr is not None else "N/A"
    res_str = f"{metrics.oi.call_resistance:.1f}" if metrics.oi.call_resistance else "N/A"
    sup_str = f"{metrics.oi.put_support:.1f}" if metrics.oi.put_support else "N/A"

    return (
        f"📊 *Option Chain Intelligence ({metrics.underlying_symbol})*\n\n"
        f"• *Spot Price*: `{metrics.spot_price:.1f}`\n"
        f"• *Put-Call Ratio (PCR)*: `{pcr_str}`\n"
        f"• *Total Call OI*: `{metrics.oi.total_call_oi:,}`\n"
        f"• *Total Put OI*: `{metrics.oi.total_put_oi:,}`\n"
        f"• *Call Resistance Strike*: `{res_str}`\n"
        f"• *Put Support Strike*: `{sup_str}`\n"
        f"• *Expiry*: `{metrics.expiry_date.strftime('%d-%b-%Y')}`"
    )


def format_trade_brief(brief: TradeBrief) -> str:
    """Format a present-moment trade brief for Telegram."""
    stamp = brief.generated_at.strftime("%d-%b %H:%M")
    valid = brief.valid_until.strftime("%H:%M")

    if brief.action == "WAIT":
        lines = [
            f"⏸ *TRADE BRIEF — WAIT* ({brief.underlying_symbol})",
            f"🕒 {stamp} IST • valid until {valid}",
            "",
            f"• *Why wait*: {brief.waiting_reason}",
        ]
        lines.extend(f"• {b}" for b in brief.rationale[:4])
        lines.append("")
        lines.append("🧭 _Decision support only — you place the trade._")
        return "\n".join(lines)

    contract = brief.contract
    name = contract.tradingsymbol if contract is not None else brief.underlying_symbol
    arrow = "🟢 BUY" if brief.action == "BUY" else "🔴 SELL"
    bias = (
        f" ({brief.underlying_direction.value.upper()} view)"
        if brief.underlying_direction is not None
        else ""
    )
    targets_str = " / ".join(f"₹{t:.1f}" for t in brief.targets)
    lots_str = (
        f"{brief.lots} lot(s)" if brief.lots is not None else "size n/a"
    )
    rr_str = f"{brief.risk_reward:.2f}" if brief.risk_reward is not None else "n/a"
    ev_str = (
        f"₹{brief.net_expected_value:,.0f}"
        if brief.net_expected_value is not None
        else "n/a"
    )
    score_str = f"{brief.score:.0f}/100" if brief.score is not None else "n/a"
    spot_str = f"{brief.spot:.1f}" if brief.spot is not None else "n/a"

    lines = [
        f"🎯 *TRADE BRIEF — {arrow} {name}*{bias}",
        f"🕒 {stamp} IST • valid until {valid}",
        "",
        f"• *Spot*: `{spot_str}`",
        f"• *Entry*: `₹{brief.entry:.2f}`",
        f"• *Stop*: `₹{brief.stop_loss:.2f}`",
        f"• *Targets*: `{targets_str}`",
        f"• *Size*: `{lots_str}`",
        f"• *R:R*: `{rr_str}` • *Net EV*: `{ev_str}` • *Score*: `{score_str}`",
        f"• *Strategy*: `{brief.strategy_name}` "
        f"• *Regime*: `{brief.regime or 'n/a'}`",
        "",
        "*Why now:*",
    ]
    lines.extend(f"• {b}" for b in brief.rationale[:5])
    if brief.warnings:
        lines.append("")
        lines.append("⚠️ *Watch-outs:*")
        lines.extend(f"• {w}" for w in brief.warnings[:3])
    lines.append("")
    lines.append(
        "🧭 _Decision support only — no auto-execution. "
        "Verify the live premium before bidding._"
    )
    return "\n".join(lines)
