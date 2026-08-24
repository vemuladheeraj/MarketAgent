"""Transaction-cost, position-sizing, expected-value, and risk-filter tests."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.config.settings import RiskConfig, TransactionCostConfig
from app.models.enums import DataQuality, Direction, SignalClassification
from app.models.risk import RiskState
from app.models.time import IST
from app.models.trading import Signal, StrategyCandidate
from app.risk import ExpectedValueEngine, PositionSizer, RiskEngine, TransactionCostModel

TS = datetime(2025, 6, 27, 15, 29, tzinfo=IST)


def _candidate(
    *,
    entry: float = 100.0,
    stop: float = 98.0,
    target: float = 104.0,
    probability: float = 0.5,
    direction: Direction = Direction.LONG,
) -> StrategyCandidate:
    return StrategyCandidate(
        strategy_name="opening_range_breakout",
        symbol="NIFTY",
        timestamp=TS,
        direction=direction,
        entry=entry,
        stop_loss=stop,
        targets=[target],
        expected_win=abs(target - entry),
        expected_loss=abs(entry - stop),
        expected_value=probability * abs(target - entry)
        - (1.0 - probability) * abs(entry - stop),
        probability=probability,
        probability_is_calibrated=False,
    )


def _signal(candidate: StrategyCandidate | None = None, *, accepted: bool = True) -> Signal:
    cand = candidate or _candidate()
    return Signal(
        candidate=cand,
        score=75.0,
        classification=SignalClassification.VALID,
        accepted=accepted,
        rejection_reasons=[] if accepted else ["score_below_minimum"],
        data_quality=DataQuality.VALID,
        timestamp=cand.timestamp,
    )


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


class TestTransactionCosts:
    def test_zero_cost_round_trip_is_zero(self):
        model = TransactionCostModel(ZERO_COSTS)
        breakdown = model.round_trip(100, 104, quantity=10, lot_size=1)
        assert breakdown.total == 0.0
        assert breakdown.notional_entry == 1000.0
        assert breakdown.notional_exit == 1040.0

    def test_stamp_duty_is_buy_side_only(self):
        cfg = TransactionCostConfig(
            brokerage=0,
            stt_buy_pct=0,
            stt_sell_pct=0,
            gst_pct=0,
            exchange_charges_pct=0,
            sebi_charges_pct=0,
            stamp_duty_pct=1.0,
            slippage_pct=0,
            bid_ask_spread_pct=0,
        )
        model = TransactionCostModel(cfg)
        long_rt = model.round_trip(100, 110, 1, direction=Direction.LONG)
        short_rt = model.round_trip(100, 90, 1, direction=Direction.SHORT)
        assert long_rt.stamp_duty == 1.0  # 1% of entry 100
        assert short_rt.stamp_duty == 0.9  # 1% of cover 90

    def test_gst_applies_to_brokerage_exchange_sebi(self):
        cfg = TransactionCostConfig(
            brokerage=1.0,
            stt_buy_pct=0,
            stt_sell_pct=0,
            gst_pct=18.0,
            exchange_charges_pct=1.0,
            sebi_charges_pct=0.0,
            stamp_duty_pct=0,
            slippage_pct=0,
            bid_ask_spread_pct=0,
        )
        model = TransactionCostModel(cfg)
        # one side notional 100: brokerage=1, exchange=1, gst=0.36
        # round trip doubles those
        breakdown = model.round_trip(100, 100, 1)
        assert abs(breakdown.brokerage - 2.0) < 1e-9
        assert abs(breakdown.exchange_charges - 2.0) < 1e-9
        assert abs(breakdown.gst - 0.72) < 1e-9


class TestPositionSizing:
    def test_quantity_is_risk_budget_over_per_unit_risk(self):
        risk = RiskConfig(account_size=100_000, risk_per_trade_pct=1.0)
        sizer = PositionSizer(risk, TransactionCostModel(ZERO_COSTS))
        # budget 1000, risk/unit 2 => 500 units
        size = sizer.size(_candidate(entry=100, stop=98, target=104))
        assert size.quantity == 500
        assert size.estimated_stop_loss == 1000.0

    def test_quantity_is_multiple_of_lot_size(self):
        risk = RiskConfig(account_size=100_000, risk_per_trade_pct=1.0)
        sizer = PositionSizer(
            risk, TransactionCostModel(ZERO_COSTS), lot_size=75
        )
        size = sizer.size(_candidate(entry=100, stop=98, target=104))
        assert size.quantity * 75 <= 500
        assert size.units == size.quantity * 75
        assert size.units % 75 == 0

    def test_costs_reduce_quantity(self):
        risk = RiskConfig(account_size=100_000, risk_per_trade_pct=1.0)
        costly = TransactionCostConfig(
            brokerage=0,
            stt_buy_pct=0,
            stt_sell_pct=0,
            gst_pct=0,
            exchange_charges_pct=0,
            sebi_charges_pct=0,
            stamp_duty_pct=0,
            slippage_pct=1.0,
            bid_ask_spread_pct=0,
        )
        with_costs = PositionSizer(risk, TransactionCostModel(costly)).size(
            _candidate(entry=100, stop=98, target=104)
        )
        without = PositionSizer(risk, TransactionCostModel(ZERO_COSTS)).size(
            _candidate(entry=100, stop=98, target=104)
        )
        assert with_costs.quantity < without.quantity
        assert with_costs.estimated_stop_loss <= with_costs.risk_budget + 1e-6

    def test_zero_when_stop_equals_cannot_size(self):
        # stop too wide versus budget
        risk = RiskConfig(account_size=1000, risk_per_trade_pct=1.0)  # budget 10
        sizer = PositionSizer(risk, TransactionCostModel(ZERO_COSTS), lot_size=75)
        size = sizer.size(_candidate(entry=100, stop=50, target=150))
        assert size.quantity == 0


class TestExpectedValue:
    def test_uninformed_prior_without_costs(self):
        costs = TransactionCostModel(ZERO_COSTS)
        engine = ExpectedValueEngine(costs)
        cand = _candidate(entry=100, stop=98, target=104, probability=0.5)
        position = PositionSizer(
            RiskConfig(account_size=100_000, risk_per_trade_pct=1.0),
            costs,
        ).size(cand)
        result, _ = engine.evaluate(cand, position)
        # win 4, loss 2, p=0.5, qty=500 -> gross EV = 0.5*2000 - 0.5*1000 = 500
        assert result.gross_win == 2000.0
        assert result.gross_loss == 1000.0
        assert abs(result.net_expected_value - 500.0) < 1e-9
        assert abs(result.gross_expected_value - 500.0) < 1e-9
        assert not result.probability_is_calibrated

    def test_costs_reduce_net_ev_versus_gross(self):
        costly = TransactionCostConfig(
            brokerage=0,
            stt_buy_pct=0,
            stt_sell_pct=0.1,
            gst_pct=0,
            exchange_charges_pct=0,
            sebi_charges_pct=0,
            stamp_duty_pct=0,
            slippage_pct=0.1,
            bid_ask_spread_pct=0.05,
        )
        costs = TransactionCostModel(costly)
        cand = _candidate()
        position = PositionSizer(
            RiskConfig(account_size=100_000, risk_per_trade_pct=1.0),
            costs,
        ).size(cand)
        result, breakdown = ExpectedValueEngine(costs).evaluate(cand, position)
        assert result.net_expected_value < result.gross_expected_value
        assert breakdown.total > 0
        assert "net_EV" in result.formula


class TestRiskEngine:
    def _engine(self, **risk_overrides) -> RiskEngine:
        risk = RiskConfig(account_size=100_000, risk_per_trade_pct=1.0, **risk_overrides)
        return RiskEngine(risk, TransactionCostModel(ZERO_COSTS), now=lambda: TS)

    def _state(self, **overrides) -> RiskState:
        base = dict(account_size=100_000, storage_available=True)
        base.update(overrides)
        return RiskState(**base)

    def test_approved_when_limits_clear(self):
        assessment = self._engine().assess(_signal(), self._state())
        assert assessment.approved
        assert assessment.position_size is not None
        assert assessment.position_size.quantity > 0
        assert assessment.expected_value is not None
        assert assessment.expected_value.net_expected_value >= 0

    def test_emergency_disable(self):
        assessment = self._engine(emergency_disable=True).assess(
            _signal(), self._state()
        )
        assert not assessment.approved
        assert "emergency_disable" in assessment.rejection_reasons

    def test_storage_unavailable_is_unsafe(self):
        assessment = self._engine().assess(
            _signal(), self._state(storage_available=False)
        )
        assert not assessment.approved
        assert "storage_unavailable" in assessment.rejection_reasons

    def test_max_daily_loss(self):
        # 3% of 100_000 = 3000
        assessment = self._engine().assess(
            _signal(), self._state(daily_realized_pnl=-3000)
        )
        assert not assessment.approved
        assert "max_daily_loss" in assessment.rejection_reasons

    def test_max_trades_and_concurrent(self):
        a = self._engine(max_trades_per_day=5).assess(
            _signal(), self._state(trades_today=5)
        )
        b = self._engine(max_concurrent_paper_trades=3).assess(
            _signal(), self._state(open_positions=3)
        )
        assert "max_trades_per_day" in a.rejection_reasons
        assert "max_concurrent_paper_trades" in b.rejection_reasons

    def test_cooldown_after_consecutive_losses(self):
        state = self._state(
            consecutive_losses=3,
            last_loss_at=TS - timedelta(minutes=10),
        )
        assessment = self._engine(
            max_consecutive_losses=3,
            cooldown_after_loss_minutes=60,
        ).assess(_signal(), state)
        assert "loss_cooldown" in assessment.rejection_reasons

        cooled = self._state(
            consecutive_losses=3,
            last_loss_at=TS - timedelta(minutes=61),
        )
        ok = self._engine(
            max_consecutive_losses=3,
            cooldown_after_loss_minutes=60,
        ).assess(_signal(), cooled)
        assert "loss_cooldown" not in ok.rejection_reasons

    def test_negative_ev_rejected(self):
        cand = _candidate(entry=100, stop=90, target=101, probability=0.5)
        # R:R = 1/10 = 0.1, also below min RR
        engine = self._engine(min_risk_reward=0.01, min_expected_value=0.0)
        assessment = engine.assess(_signal(cand), self._state())
        assert "expected_value_below_minimum" in assessment.rejection_reasons
        assert not assessment.approved

    def test_unaccepted_signal_rejected(self):
        assessment = self._engine().assess(
            _signal(accepted=False), self._state()
        )
        assert "signal_not_accepted" in assessment.rejection_reasons
        assert not assessment.approved
