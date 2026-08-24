"""Position sizing from maximum acceptable risk.

Quantity is the largest lot-multiple whose estimated stop-out loss, including
round-trip costs, does not exceed ``account_size * risk_per_trade_pct / 100``.
"""

from __future__ import annotations

from app.config.settings import RiskConfig
from app.models.risk import PositionSize
from app.models.trading import StrategyCandidate
from app.risk.costs import TransactionCostModel


class PositionSizer:
    def __init__(
        self,
        risk: RiskConfig,
        costs: TransactionCostModel,
        *,
        lot_size: int = 1,
        point_value: float = 1.0,
    ) -> None:
        self.risk = risk
        self.costs = costs
        self.lot_size = max(1, lot_size)
        self.point_value = point_value

    def size(
        self,
        candidate: StrategyCandidate,
        *,
        account_size: float | None = None,
    ) -> PositionSize:
        account = account_size if account_size is not None else self.risk.account_size
        risk_budget = account * self.risk.risk_per_trade_pct / 100.0
        risk_per_unit = candidate.risk_per_unit
        risk_per_lot = risk_per_unit * self.lot_size * self.point_value
        if risk_per_lot <= 0:
            return self._empty(account, risk_budget, risk_per_unit)

        max_lots = int(risk_budget // risk_per_lot)
        quantity = self._fit_after_costs(candidate, max_lots, risk_budget)
        stop_loss = 0.0
        if quantity > 0:
            stop_loss = self._stop_out_loss(candidate, quantity)
        return PositionSize(
            quantity=quantity,
            lot_size=self.lot_size,
            point_value=self.point_value,
            risk_budget=risk_budget,
            risk_per_unit=risk_per_unit,
            estimated_stop_loss=stop_loss,
            account_size=account,
            risk_per_trade_pct=self.risk.risk_per_trade_pct,
        )

    def _fit_after_costs(
        self,
        candidate: StrategyCandidate,
        max_lots: int,
        risk_budget: float,
    ) -> int:
        low, high = 0, max_lots
        best = 0
        while low <= high:
            mid = (low + high) // 2
            if mid == 0 or self._stop_out_loss(candidate, mid) <= risk_budget + 1e-9:
                best = mid
                low = mid + 1
            else:
                high = mid - 1
        return best

    def _stop_out_loss(self, candidate: StrategyCandidate, quantity: int) -> float:
        gross = candidate.risk_per_unit * quantity * self.lot_size * self.point_value
        costs = self.costs.round_trip(
            candidate.entry,
            candidate.stop_loss,
            quantity,
            lot_size=self.lot_size,
            point_value=self.point_value,
            direction=candidate.direction,
        )
        return gross + costs.total

    def _empty(self, account: float, risk_budget: float, risk_per_unit: float) -> PositionSize:
        return PositionSize(
            quantity=0,
            lot_size=self.lot_size,
            point_value=self.point_value,
            risk_budget=risk_budget,
            risk_per_unit=risk_per_unit,
            estimated_stop_loss=0.0,
            account_size=account,
            risk_per_trade_pct=self.risk.risk_per_trade_pct,
        )
