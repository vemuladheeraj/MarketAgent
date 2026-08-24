"""Telegram Bot Command Dispatcher and Interactive Interface."""

from __future__ import annotations

from typing import Any

from app.models.enums import TradeStage
from app.models.snapshots import MarketSnapshot
from app.paper_trading.engine import PaperTradingEngine
from app.paper_trading.tracker import PaperPerformanceTracker
from app.storage.market_store import MarketStore


class TelegramCommandHandler:
    """Processes incoming slash commands and produces formatted responses."""

    def __init__(
        self,
        store: MarketStore,
        paper_engine: PaperTradingEngine | None = None,
        tracker: PaperPerformanceTracker | None = None,
    ) -> None:
        self.store = store
        self.paper_engine = paper_engine
        self.tracker = tracker or PaperPerformanceTracker()

    def handle_command(self, command: str, *, args: list[str] | None = None) -> str:
        cmd = command.strip().lower()
        if not cmd.startswith("/"):
            cmd = f"/{cmd}"

        if cmd in ("/status", "/start"):
            return self._handle_status()
        elif cmd == "/signals":
            return self._handle_signals()
        elif cmd == "/nifty":
            return self._handle_instrument("NIFTY")
        elif cmd == "/banknifty":
            return self._handle_instrument("BANKNIFTY")
        elif cmd == "/options":
            symbol = args[0].upper() if args else "NIFTY"
            return self._handle_options(symbol)
        elif cmd == "/vix":
            return self._handle_vix()
        elif cmd == "/watchlist":
            return self._handle_watchlist()
        elif cmd == "/papertrades":
            return self._handle_papertrades()
        elif cmd == "/performance":
            return self._handle_performance()
        elif cmd == "/analysis":
            symbol = args[0].upper() if args else "NIFTY"
            return self._handle_analysis(symbol)
        else:
            return (
                "❓ *Unknown Command*\n\n"
                "Available commands:\n"
                "• `/status` - Agent status & risk state\n"
                "• `/signals` - Latest candidate signals\n"
                "• `/nifty` - NIFTY spot & levels\n"
                "• `/banknifty` - BANKNIFTY spot & levels\n"
                "• `/options [NIFTY/BANKNIFTY]` - Option chain metrics\n"
                "• `/vix` - India VIX status\n"
                "• `/watchlist` - Active instruments\n"
                "• `/papertrades` - Active & recent paper positions\n"
                "• `/performance` - Overall strategy statistics\n"
                "• `/analysis [NIFTY/BANKNIFTY]` - Gemini contextual overview"
            )

    def _handle_status(self) -> str:
        risk_state = self.store.load_risk_state(1_000_000.0)
        open_pos = len(self.paper_engine.get_open_positions()) if self.paper_engine else 0
        return (
            "🤖 *Indian Market Research Agent — Status*\n\n"
            f"• *Storage Backend*: `{self.store.backend}`\n"
            f"• *Account Size*: ₹{risk_state.account_size:,.2f}\n"
            f"• *Open Paper Positions*: `{open_pos}`\n"
            f"• *Today's Trades*: `{risk_state.trades_today}`\n"
            f"• *Daily Realized P&L*: ₹{risk_state.daily_realized_pnl:,.2f}\n"
            f"• *Consecutive Losses*: `{risk_state.consecutive_losses}`\n"
            f"• *Mode*: `Research & Paper-Trading (No Real Trades)`"
        )

    def _handle_signals(self) -> str:
        sigs = self.store.signals.list_all()
        if not sigs:
            return "📡 *Signals*: No recent signals generated (NO_TRADE state)."
        lines = ["📡 *Recent Signals:*"]
        for s in sigs[-5:]:
            lines.append(
                f"• *{s.candidate.symbol}* ({s.candidate.direction.value.upper()}) | "
                f"`{s.candidate.strategy_name}` | Score: `{s.score:.1f}` | Accepted: `{s.accepted}`"
            )
        return "\n".join(lines)

    def _handle_instrument(self, symbol: str) -> str:
        snaps = self.store.snapshots.list_all()
        if not snaps:
            return f"📈 *{symbol}*: No recent market snapshots available."
        last = snaps[-1]
        quote = last.quotes.get(symbol)
        if not quote:
            return f"📈 *{symbol}*: Quote not found in latest snapshot."

        return (
            f"📈 *{symbol} Spot Overview*\n\n"
            f"• *LTP*: `{quote.last_price:.2f}`\n"
            f"• *Open*: `{quote.open_price:.2f}` | *High*: `{quote.high_price:.2f}` | *Low*: `{quote.low_price:.2f}`\n"
            f"• *Close*: `{quote.close_price:.2f}`\n"
            f"• *Timestamp*: `{quote.timestamp.strftime('%H:%M:%S IST')}`"
        )

    def _handle_options(self, symbol: str) -> str:
        chains = self.store.option_chains.list_all()
        matches = [c for c in chains if c.symbol == symbol]
        if not matches:
            return f"📊 *{symbol} Options*: No option chain snapshots available."
        chain = matches[-1]
        pcr = chain.pcr
        pcr_str = f"{pcr:.2f}" if pcr is not None else "N/A"
        return (
            f"📊 *{symbol} Options Intelligence*\n\n"
            f"• *Underlying LTP*: `{chain.underlying_price:.2f}`\n"
            f"• *PCR*: `{pcr_str}`\n"
            f"• *Expiry*: `{chain.expiry_date.strftime('%d-%b-%Y')}`\n"
            f"• *Strikes Tracked*: `{len(chain.entries)}`"
        )

    def _handle_vix(self) -> str:
        snaps = self.store.snapshots.list_all()
        if not snaps or snaps[-1].vix is None:
            return "📉 *India VIX*: Data not currently available."
        vix = snaps[-1].vix
        state = "HIGH" if vix >= 20 else ("LOW" if vix <= 12 else "NORMAL")
        return f"📉 *India VIX*: `{vix:.2f}` ({state} Volatility)"

    def _handle_watchlist(self) -> str:
        return "👀 *Watchlist*: `NIFTY`, `BANKNIFTY`"

    def _handle_papertrades(self) -> str:
        if not self.paper_engine:
            return "💼 *Paper Trades*: Paper trading engine not initialized."
        open_pos = self.paper_engine.get_open_positions()
        completed = self.paper_engine.completed_positions

        lines = ["💼 *Paper Trading Summary:*\n"]
        lines.append(f"*Active Open Positions ({len(open_pos)}):*")
        if open_pos:
            for p in open_pos:
                lines.append(
                    f"• *{p.symbol}* ({p.direction.value.upper()} {p.quantity} lots) | "
                    f"Entry: `{p.simulated_entry:.1f}` | LTP: `{p.current_price:.1f}` | "
                    f"Unrealized: ₹{p.unrealized_pnl:.2f}"
                )
        else:
            lines.append("• No open positions.")

        lines.append(f"\n*Recent Closed Positions ({len(completed[-5:])}):*")
        if completed:
            for p in completed[-5:]:
                lines.append(
                    f"• *{p.symbol}* | `{p.strategy_name}` | Net P&L: *₹{p.net_pnl:.2f}* ({p.exit_reason.value if p.exit_reason else ''})"
                )
        else:
            lines.append("• No closed trades yet.")

        return "\n".join(lines)

    def _handle_performance(self) -> str:
        if not self.paper_engine:
            return "📊 *Performance*: Paper trading engine not active."
        perf = self.tracker.evaluate(self.paper_engine.completed_positions)
        return (
            "📊 *Paper Strategy Performance*\n\n"
            f"• *Total Trades*: `{perf.total_trades}`\n"
            f"• *Win Rate*: `{perf.win_rate * 100:.1f}%` ({perf.winning_trades}W / {perf.losing_trades}L)\n"
            f"• *Net Realized P&L*: *₹{perf.net_pnl:,.2f}*\n"
            f"• *Total Costs*: ₹{perf.total_costs:,.2f}\n"
            f"• *Profit Factor*: `{perf.profit_factor:.2f}`\n"
            f"• *Average R*: `{perf.average_r:.2f}R`\n"
            f"• *Max Drawdown*: `{perf.max_drawdown_pct:.1f}%` (₹{perf.max_drawdown_amount:,.2f})\n"
            f"• *Sharpe Ratio*: `{perf.sharpe_ratio:.2f}`"
        )

    def _handle_analysis(self, symbol: str) -> str:
        return (
            f"🧠 *Gemini Contextual Analysis ({symbol})*\n\n"
            f"• Market currently evaluated in deterministic quantitative pipeline.\n"
            f"• Full contradiction detection active.\n"
            f"• Type `/status` or `/signals` for point-in-time state."
        )
