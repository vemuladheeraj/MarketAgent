"""Risk filters: position size, costs, expected value, and book limits.

A Firestore/storage failure is treated as unsafe: new paper entries are
rejected rather than sized without a reliable risk book.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from app.config.settings import RiskConfig
from app.logging.setup import get_logger, log_event
from app.models.enums import DataQuality, SystemEventType
from app.models.risk import RiskAssessment, RiskState
from app.models.time import now_ist
from app.models.trading import Signal
from app.risk.costs import TransactionCostModel
from app.risk.expected_value import ExpectedValueEngine
from app.risk.position_sizing import PositionSizer


class RiskEngine:
    def __init__(
        self,
        risk: RiskConfig,
        costs: TransactionCostModel,
        *,
        lot_size: int = 1,
        point_value: float = 1.0,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.risk = risk
        self.sizer = PositionSizer(
            risk, costs, lot_size=lot_size, point_value=point_value
        )
        self.ev = ExpectedValueEngine(costs)
        self._now = now or now_ist
        self._logger = get_logger("risk")

    def assess(self, signal: Signal, state: RiskState) -> RiskAssessment:
        reasons: list[str] = []
        candidate = signal.candidate
        position = self.sizer.size(candidate, account_size=state.account_size)
        ev_result, round_trip = self.ev.evaluate(candidate, position)
        now = self._now()

        if self.risk.emergency_disable:
            reasons.append("emergency_disable")
        if not state.storage_available:
            reasons.append("storage_unavailable")
        if signal.data_quality == DataQuality.INVALID:
            reasons.append("data_quality_invalid")
        if not signal.accepted:
            reasons.append("signal_not_accepted")
        if candidate.risk_reward < self.risk.min_risk_reward:
            reasons.append("risk_reward_below_minimum")
        if ev_result.net_expected_value < self.risk.min_expected_value:
            reasons.append("expected_value_below_minimum")
        if position.quantity <= 0:
            reasons.append("position_size_zero")
        if state.trades_today >= self.risk.max_trades_per_day:
            reasons.append("max_trades_per_day")
        if state.open_positions >= self.risk.max_concurrent_paper_trades:
            reasons.append("max_concurrent_paper_trades")
        if self._daily_loss_breached(state):
            reasons.append("max_daily_loss")
        if self._cooldown_active(state, now):
            reasons.append("loss_cooldown")

        approved = not reasons
        if not approved:
            log_event(
                self._logger,
                SystemEventType.RISK_REJECTED.value.upper(),
                "risk engine rejected candidate",
                strategy=candidate.strategy_name,
                symbol=candidate.symbol,
                reasons=",".join(reasons),
            )
        return RiskAssessment(
            approved=approved,
            timestamp=candidate.timestamp,
            symbol=candidate.symbol,
            strategy_name=candidate.strategy_name,
            rejection_reasons=reasons,
            position_size=position,
            expected_value=ev_result,
            round_trip_cost=round_trip,
        )

    def _daily_loss_breached(self, state: RiskState) -> bool:
        cap = state.account_size * self.risk.max_daily_loss_pct / 100.0
        return state.daily_realized_pnl <= -cap

    def _cooldown_active(self, state: RiskState, now: datetime) -> bool:
        if state.consecutive_losses < self.risk.max_consecutive_losses:
            return False
        if self.risk.cooldown_after_loss_minutes <= 0:
            return True
        if state.last_loss_at is None:
            return True
        elapsed = now - state.last_loss_at
        return elapsed < timedelta(minutes=self.risk.cooldown_after_loss_minutes)
