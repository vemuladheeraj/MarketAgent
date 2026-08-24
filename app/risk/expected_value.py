"""Transparent expected-value calculation including costs and slippage.

EV uses the candidate probability as supplied. Until that probability is
historically calibrated, a positive EV is a structural number, not a claim
of edge.
"""

from __future__ import annotations

from app.models.risk import CostBreakdown, ExpectedValueResult, PositionSize
from app.models.trading import StrategyCandidate
from app.risk.costs import TransactionCostModel


class ExpectedValueEngine:
    def __init__(self, costs: TransactionCostModel) -> None:
        self.costs = costs

    def evaluate(
        self,
        candidate: StrategyCandidate,
        position: PositionSize,
    ) -> tuple[ExpectedValueResult, CostBreakdown]:
        units_scale = position.quantity * position.lot_size * position.point_value
        p = candidate.probability
        gross_win = candidate.expected_win * units_scale
        gross_loss = candidate.expected_loss * units_scale
        first_target = candidate.targets[0]
        cost_win = self.costs.round_trip(
            candidate.entry,
            first_target,
            position.quantity,
            lot_size=position.lot_size,
            point_value=position.point_value,
            direction=candidate.direction,
        )
        cost_loss = self.costs.round_trip(
            candidate.entry,
            candidate.stop_loss,
            position.quantity,
            lot_size=position.lot_size,
            point_value=position.point_value,
            direction=candidate.direction,
        )
        net_win = gross_win - cost_win.total
        net_loss = gross_loss + cost_loss.total
        gross_ev = p * gross_win - (1.0 - p) * gross_loss
        net_ev = p * net_win - (1.0 - p) * net_loss
        risk = position.estimated_stop_loss or net_loss or 0.0
        expectancy_r = 0.0 if risk <= 0 else net_ev / risk
        formula = (
            f"gross_EV = p*gross_win - (1-p)*gross_loss ; "
            f"net_EV = p*(gross_win - cost_win) - (1-p)*(gross_loss + cost_loss) ; "
            f"p={p}"
        )
        result = ExpectedValueResult(
            probability=p,
            probability_is_calibrated=candidate.probability_is_calibrated,
            gross_win=gross_win,
            gross_loss=gross_loss,
            cost_if_win=cost_win.total,
            cost_if_loss=cost_loss.total,
            net_win=net_win,
            net_loss=net_loss,
            gross_expected_value=gross_ev,
            net_expected_value=net_ev,
            expectancy_r=expectancy_r,
            risk_reward=candidate.risk_reward,
            formula=formula,
        )
        return result, cost_win
