"""Real-time Paper Trading Engine.

Manages the active lifecycle of paper positions:
SIGNAL -> PAPER_ENTRY -> MONITOR -> EXIT -> RESULT

Tracks unrealized P&L, MFE/MAE, executes stop-loss and targets, calculates
realistic round-trip Indian transaction costs, and synchronizes risk state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from app.logging.setup import get_logger, log_event
from app.models.backtesting import BacktestTrade, ExitReason
from app.models.candle import MarketCandle, MarketQuote
from app.models.enums import Direction, SystemEventType, TradeStage
from app.models.paper_trading import PaperPosition
from app.models.risk import RiskAssessment, RiskState
from app.models.time import now_ist
from app.models.trading import Signal
from app.risk.costs import TransactionCostModel
from app.storage.market_store import MarketStore


class PaperTradingEngine:
    """Live state manager and execution simulator for paper trading."""

    def __init__(
        self,
        store: MarketStore,
        cost_model: TransactionCostModel,
        *,
        default_account_size: float = 1_000_000.0,
        lot_size: int = 1,
        point_value: float = 1.0,
    ) -> None:
        self.store = store
        self.cost_model = cost_model
        self.default_account_size = default_account_size
        self.lot_size = lot_size
        self.point_value = point_value
        self._active_positions: dict[str, PaperPosition] = {}
        self._completed_positions: list[PaperPosition] = []
        self._logger = get_logger("paper_trading")

    @property
    def active_positions(self) -> dict[str, PaperPosition]:
        return dict(self._active_positions)

    @property
    def completed_positions(self) -> list[PaperPosition]:
        return list(self._completed_positions)

    def open_position(
        self,
        signal: Signal,
        assessment: RiskAssessment,
        *,
        execution_price: float | None = None,
        execution_time: datetime | None = None,
        regime: str | None = None,
    ) -> PaperPosition | None:
        """Create and open a new active paper trading position from an approved signal."""
        if not assessment.approved or assessment.position_size is None or assessment.position_size.quantity <= 0:
            log_event(
                self._logger,
                "RISK_REJECTED",
                "cannot open paper position: risk assessment not approved",
                symbol=signal.candidate.symbol,
                strategy=signal.candidate.strategy_name,
            )
            return None

        t0 = execution_time or signal.candidate.timestamp
        cand = signal.candidate
        pos_size = assessment.position_size
        entry_px = execution_price if execution_price is not None else cand.entry

        position = PaperPosition(
            position_id=f"pos_{uuid.uuid4().hex[:8]}",
            signal_id=None,
            strategy_name=cand.strategy_name,
            symbol=cand.symbol,
            direction=cand.direction,
            stage=TradeStage.MONITOR,
            planned_entry=cand.entry,
            simulated_entry=entry_px,
            entry_time=t0,
            quantity=pos_size.quantity,
            lot_size=pos_size.lot_size,
            point_value=pos_size.point_value,
            stop_loss=cand.stop_loss,
            targets=list(cand.targets),
            current_price=entry_px,
            unrealized_pnl=0.0,
            mae=0.0,
            mfe=0.0,
            regime=cand.factors.get("regime"),
            signal_score=signal.score,
            open_time=t0,
            last_update_time=t0,
            metadata={"explanation": cand.explanation},
        )

        self._active_positions[position.position_id] = position

        # Synchronize risk state
        risk_state = self.store.load_risk_state(self.default_account_size)
        risk_state.open_positions = len(self._active_positions)
        risk_state.trades_today += 1
        self.store.save_risk_state(risk_state)

        log_event(
            self._logger,
            SystemEventType.PAPER_TRADE_OPENED.value.upper(),
            "paper position opened",
            position_id=position.position_id,
            strategy=position.strategy_name,
            symbol=position.symbol,
            direction=position.direction.value,
            entry=position.simulated_entry,
            quantity=position.quantity,
            stop=position.stop_loss,
            target=position.targets[0] if position.targets else 0.0,
        )

        return position

    def update_with_quote(self, quote: MarketQuote) -> list[PaperPosition]:
        """Update live open positions matching the quote's symbol and check for exits."""
        closed: list[PaperPosition] = []
        now = quote.timestamp

        for pos_id, pos in list(self._active_positions.items()):
            if pos.symbol != quote.symbol:
                continue

            last_px = quote.last_price
            pos.current_price = last_px
            pos.last_update_time = now

            # Update MAE and MFE
            self._update_excursion(pos, last_px)

            # Update unrealized PnL
            units = pos.quantity * pos.lot_size
            if pos.direction == Direction.LONG:
                pos.unrealized_pnl = (last_px - pos.simulated_entry) * units * pos.point_value
            else:
                pos.unrealized_pnl = (pos.simulated_entry - last_px) * units * pos.point_value

            # Check Stop Loss
            if pos.direction == Direction.LONG and last_px <= pos.stop_loss:
                closed_pos = self.close_position(pos_id, exit_price=pos.stop_loss, exit_reason=ExitReason.STOP_LOSS, exit_time=now)
                if closed_pos:
                    closed.append(closed_pos)
            elif pos.direction == Direction.SHORT and last_px >= pos.stop_loss:
                closed_pos = self.close_position(pos_id, exit_price=pos.stop_loss, exit_reason=ExitReason.STOP_LOSS, exit_time=now)
                if closed_pos:
                    closed.append(closed_pos)
            # Check Profit Target
            elif pos.targets:
                target = pos.targets[0]
                if pos.direction == Direction.LONG and last_px >= target:
                    closed_pos = self.close_position(pos_id, exit_price=target, exit_reason=ExitReason.TARGET, exit_time=now)
                    if closed_pos:
                        closed.append(closed_pos)
                elif pos.direction == Direction.SHORT and last_px <= target:
                    closed_pos = self.close_position(pos_id, exit_price=target, exit_reason=ExitReason.TARGET, exit_time=now)
                    if closed_pos:
                        closed.append(closed_pos)

        return closed

    def update_with_candle(self, candle: MarketCandle, *, pessimistic: bool = True) -> list[PaperPosition]:
        """Update open positions against candle high/low range."""
        closed: list[PaperPosition] = []
        now = candle.timestamp

        for pos_id, pos in list(self._active_positions.items()):
            if pos.symbol != candle.symbol:
                continue

            pos.current_price = candle.close_price
            pos.last_update_time = now

            # Update MAE and MFE from High/Low
            if pos.direction == Direction.LONG:
                fav = max(0.0, candle.high_price - pos.simulated_entry)
                adv = max(0.0, pos.simulated_entry - candle.low_price)
            else:
                fav = max(0.0, pos.simulated_entry - candle.low_price)
                adv = max(0.0, candle.high_price - pos.simulated_entry)

            if adv > pos.mae:
                pos.mae = adv
            if fav > pos.mfe:
                pos.mfe = fav

            # Check exits
            target = pos.targets[0] if pos.targets else None

            if pos.direction == Direction.LONG:
                hit_stop = candle.low_price <= pos.stop_loss
                hit_target = target is not None and candle.high_price >= target

                if hit_stop and hit_target:
                    exit_px = pos.stop_loss if pessimistic else target
                    reason = ExitReason.STOP_LOSS if pessimistic else ExitReason.TARGET
                    c_pos = self.close_position(pos_id, exit_price=exit_px, exit_reason=reason, exit_time=now)
                    if c_pos:
                        closed.append(c_pos)
                elif hit_stop:
                    c_pos = self.close_position(pos_id, exit_price=min(candle.open_price, pos.stop_loss), exit_reason=ExitReason.STOP_LOSS, exit_time=now)
                    if c_pos:
                        closed.append(c_pos)
                elif hit_target and target is not None:
                    c_pos = self.close_position(pos_id, exit_price=max(candle.open_price, target), exit_reason=ExitReason.TARGET, exit_time=now)
                    if c_pos:
                        closed.append(c_pos)

            else:  # SHORT
                hit_stop = candle.high_price >= pos.stop_loss
                hit_target = target is not None and candle.low_price <= target

                if hit_stop and hit_target:
                    exit_px = pos.stop_loss if pessimistic else target
                    reason = ExitReason.STOP_LOSS if pessimistic else ExitReason.TARGET
                    c_pos = self.close_position(pos_id, exit_price=exit_px, exit_reason=reason, exit_time=now)
                    if c_pos:
                        closed.append(c_pos)
                elif hit_stop:
                    c_pos = self.close_position(pos_id, exit_price=max(candle.open_price, pos.stop_loss), exit_reason=ExitReason.STOP_LOSS, exit_time=now)
                    if c_pos:
                        closed.append(c_pos)
                elif hit_target and target is not None:
                    c_pos = self.close_position(pos_id, exit_price=min(candle.open_price, target), exit_reason=ExitReason.TARGET, exit_time=now)
                    if c_pos:
                        closed.append(c_pos)

        return closed

    def close_position(
        self,
        position_id: str,
        *,
        exit_price: float,
        exit_reason: ExitReason,
        exit_time: datetime | None = None,
    ) -> PaperPosition | None:
        """Close an active paper position, deduct costs, and record final results."""
        pos = self._active_positions.pop(position_id, None)
        if pos is None:
            return None

        t_exit = exit_time or now_ist()
        units = pos.quantity * pos.lot_size

        if pos.direction == Direction.LONG:
            gross_pnl = (exit_price - pos.simulated_entry) * units * pos.point_value
        else:
            gross_pnl = (pos.simulated_entry - exit_price) * units * pos.point_value

        cost = self.cost_model.round_trip(
            entry=pos.simulated_entry,
            exit_price=exit_price,
            quantity=pos.quantity,
            lot_size=pos.lot_size,
            point_value=pos.point_value,
            direction=pos.direction,
        )

        net_pnl = gross_pnl - cost.total
        init_risk = abs(pos.simulated_entry - pos.stop_loss) * units * pos.point_value
        r_multiple = (net_pnl / init_risk) if init_risk > 0 else 0.0

        pos.stage = TradeStage.RESULT
        pos.exit_time = t_exit
        pos.exit_price = round(exit_price, 4)
        pos.exit_reason = exit_reason
        pos.gross_pnl = round(gross_pnl, 4)
        pos.net_pnl = round(net_pnl, 4)
        pos.cost = cost
        pos.r_multiple = round(r_multiple, 4)
        pos.unrealized_pnl = 0.0

        self._completed_positions.append(pos)

        # Update RiskState
        risk_state = self.store.load_risk_state(self.default_account_size)
        risk_state.open_positions = len(self._active_positions)
        risk_state.daily_realized_pnl += net_pnl
        if net_pnl < 0:
            risk_state.consecutive_losses += 1
            risk_state.last_loss_at = t_exit
        elif net_pnl > 0:
            risk_state.consecutive_losses = 0
        self.store.save_risk_state(risk_state)

        log_event(
            self._logger,
            SystemEventType.PAPER_TRADE_CLOSED.value.upper(),
            "paper position closed",
            position_id=pos.position_id,
            strategy=pos.strategy_name,
            symbol=pos.symbol,
            exit_price=pos.exit_price,
            reason=pos.exit_reason.value,
            gross_pnl=pos.gross_pnl,
            net_pnl=pos.net_pnl,
            total_cost=cost.total,
        )

        return pos

    def _update_excursion(self, pos: PaperPosition, current_price: float) -> None:
        if pos.direction == Direction.LONG:
            fav = max(0.0, current_price - pos.simulated_entry)
            adv = max(0.0, pos.simulated_entry - current_price)
        else:
            fav = max(0.0, pos.simulated_entry - current_price)
            adv = max(0.0, current_price - pos.simulated_entry)

        if adv > pos.mae:
            pos.mae = round(adv, 4)
        if fav > pos.mfe:
            pos.mfe = round(fav, 4)

    def get_open_positions(self) -> list[PaperPosition]:
        return list(self._active_positions.values())

    def get_completed_trades(self) -> list[BacktestTrade]:
        return [p.to_completed_trade() for p in self._completed_positions]
