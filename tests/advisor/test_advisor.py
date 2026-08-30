"""Unit tests for the TradeAdvisor (present-moment trade briefs)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from app.advisor.advisor import TradeAdvisor
from app.analysis.regime.classifier import RegimeAssessment
from app.config.settings import AdvisorConfig, FirestoreConfig
from app.models.advisor import OptionContractRef, TradeBrief
from app.models.enums import (
    DataQuality,
    Direction,
    MarketRegime,
    OptionType,
    SignalClassification,
)
from app.models.options import OptionChainEntry, OptionChainSnapshot
from app.models.options_analysis import OptionGreeks, OptionMetrics
from app.models.risk import ExpectedValueResult, PositionSize, RiskAssessment
from app.models.time import IST
from app.models.trading import Signal, StrategyCandidate
from app.storage.market_store import MarketStore

EXPIRY = datetime(2099, 1, 30, 15, 30, tzinfo=IST)
NOW = datetime(2099, 1, 30, 10, 0, 0, tzinfo=IST)


def make_chain() -> OptionChainSnapshot:
    entries = []
    for strike, call_ltp, put_ltp in [
        (24700, 90.0, 60.0),
        (24750, 180.0, 95.0),
        (24800, 120.0, 160.0),
    ]:
        for option_type, ltp in (
            (OptionType.CALL, call_ltp),
            (OptionType.PUT, put_ltp),
        ):
            entries.append(
                OptionChainEntry(
                    strike=strike,
                    option_type=option_type,
                    expiry_date=EXPIRY,
                    open_interest=120_000 if option_type == OptionType.CALL else 100_000,
                    change_in_oi=5_000,
                    last_price=ltp,
                    bid=ltp - 2,
                    ask=ltp + 2,
                    iv=0.13,
                )
            )
    return OptionChainSnapshot(
        underlying_symbol="NIFTY",
        timestamp=NOW,
        spot_price=24752.0,
        expiry_date=EXPIRY,
        entries=entries,
    )


def make_metrics() -> OptionMetrics:
    return OptionMetrics(
        underlying_symbol="NIFTY",
        timestamp=NOW,
        expiry_date=EXPIRY,
        spot_price=24752.0,
        greeks={
            "24750CE": OptionGreeks(delta=0.52, iv=0.13),
            "24750PE": OptionGreeks(delta=-0.48, iv=0.14),
        },
        atm_strike=24750.0,
    )


def make_candidate(
    direction: Direction = Direction.LONG,
    entry: float = 24760.0,
    stop: float = 24710.0,
    targets: tuple[float, ...] = (24840.0,),
) -> StrategyCandidate:
    return StrategyCandidate(
        strategy_name="vwap_momentum",
        symbol="NIFTY",
        timestamp=NOW,
        direction=direction,
        entry=entry,
        stop_loss=stop,
        targets=list(targets),
        expected_win=1.6,
        expected_loss=1.0,
        expected_value=0.3,
        probability=0.55,
        explanation="Price is above VWAP with supportive momentum.",
    )


def make_signal(direction: Direction = Direction.LONG, score: float = 82.0) -> Signal:
    return Signal(
        candidate=make_candidate(direction=direction),
        score=score,
        classification=SignalClassification.HIGH_QUALITY,
        accepted=True,
        timestamp=NOW,
    )


def make_risk() -> RiskAssessment:
    return RiskAssessment(
        approved=True,
        timestamp=NOW,
        symbol="NIFTY",
        strategy_name="vwap_momentum",
        position_size=PositionSize(
            quantity=2,
            lot_size=75,
            point_value=1.0,
            risk_budget=10_000.0,
            risk_per_unit=50.0,
            estimated_stop_loss=9_800.0,
            account_size=1_000_000.0,
            risk_per_trade_pct=1.0,
        ),
        expected_value=ExpectedValueResult(
            probability=0.55,
            gross_win=8_000.0,
            gross_loss=-5_000.0,
            cost_if_win=150.0,
            cost_if_loss=150.0,
            net_win=7_850.0,
            net_loss=-5_150.0,
            gross_expected_value=2_075.0,
            net_expected_value=1_982.5,
            expectancy_r=0.41,
            risk_reward=1.6,
        ),
    )


def make_regime() -> RegimeAssessment:
    return RegimeAssessment(
        symbol="NIFTY",
        timestamp=NOW,
        regime=MarketRegime.STRONG_UPTREND,
        confidence=0.8,
        trend_score=0.9,
        reasons=["price above SMA20", "ADX strong"],
    )


class TestTradeBriefModel:
    def test_wait_requires_reason(self) -> None:
        with pytest.raises(ValidationError):
            TradeBrief(
                generated_at=NOW,
                valid_until=NOW + timedelta(minutes=5),
                action="WAIT",
                underlying_symbol="NIFTY",
            )

    def test_actionable_requires_contract_and_levels(self) -> None:
        with pytest.raises(ValidationError):
            TradeBrief(
                generated_at=NOW,
                valid_until=NOW + timedelta(minutes=5),
                action="BUY",
                underlying_symbol="NIFTY",
                entry=100.0,
                stop_loss=90.0,
                targets=[120.0],
            )

    def test_actionable_buy_requires_stop_below_entry(self) -> None:
        with pytest.raises(ValidationError):
            TradeBrief(
                generated_at=NOW,
                valid_until=NOW + timedelta(minutes=5),
                action="BUY",
                underlying_symbol="NIFTY",
                contract=OptionContractRef(
                    tradingsymbol="NIFTY 24750 CE",
                    strike=24750.0,
                    option_type=OptionType.CALL,
                    expiry_date=EXPIRY,
                    last_price=100.0,
                ),
                entry=100.0,
                stop_loss=110.0,
                targets=[130.0],
            )


class TestTradeAdvisor:
    def test_long_buys_atm_call_with_delta_translated_premiums(self) -> None:
        advisor = TradeAdvisor(AdvisorConfig())
        brief = advisor.build_brief(
            signal=make_signal(),
            risk=make_risk(),
            chain=make_chain(),
            metrics=make_metrics(),
            regime=make_regime(),
            generated_at=NOW,
        )
        assert brief is not None
        assert brief.action == "BUY"
        assert brief.underlying_direction == Direction.LONG
        assert brief.contract is not None
        assert brief.contract.strike == 24750.0
        assert brief.contract.option_type == OptionType.CALL
        assert brief.contract.tradingsymbol == "NIFTY 24750CE"
        # Index risk 50 pts x delta 0.52 = 26 premium risk -> stop 154.0
        assert brief.entry == 180.0
        assert brief.stop_loss == pytest.approx(154.0, abs=0.01)
        # Index reward 80 pts x 0.52 = 41.6 -> target 221.6
        assert brief.targets[0] == pytest.approx(221.6, abs=0.01)
        assert brief.risk_reward == pytest.approx(1.6, abs=0.01)
        assert brief.lots == 2
        assert brief.risk_amount == pytest.approx(9_800.0)
        assert brief.net_expected_value == pytest.approx(1_982.5)
        assert brief.valid_until == NOW + timedelta(minutes=10)
        assert any("PCR" in r for r in brief.rationale)

    def test_short_buys_atm_put(self) -> None:
        advisor = TradeAdvisor(AdvisorConfig())
        candidate = make_candidate(
            direction=Direction.SHORT, entry=24740.0, stop=24790.0, targets=(24660.0,)
        )
        signal = Signal(
            candidate=candidate,
            score=78.0,
            classification=SignalClassification.VALID,
            accepted=True,
            timestamp=NOW,
        )
        brief = advisor.build_brief(
            signal=signal,
            risk=make_risk(),
            chain=make_chain(),
            metrics=make_metrics(),
            generated_at=NOW,
        )
        assert brief is not None
        assert brief.contract is not None
        assert brief.contract.option_type == OptionType.PUT
        assert brief.contract.strike == 24750.0
        # risk 50 x 0.48 = 24 -> stop 95-24 = 71.0; reward 80 x 0.48 = 38.4 -> 133.4
        assert brief.entry == 95.0
        assert brief.stop_loss == pytest.approx(71.0, abs=0.01)
        assert brief.targets[0] == pytest.approx(133.4, abs=0.01)

    def test_delta_missing_falls_back_to_premium_ratio(self) -> None:
        advisor = TradeAdvisor(AdvisorConfig())
        brief = advisor.build_brief(
            signal=make_signal(),
            risk=make_risk(),
            chain=make_chain(),
            metrics=None,
            generated_at=NOW,
        )
        assert brief is not None
        assert any("Delta unavailable" in w for w in brief.warnings)
        scale = 180.0 / 24752.0
        assert brief.stop_loss == pytest.approx(180.0 - 50.0 * scale, abs=0.01)

    def test_premium_too_small_for_setup_risk_returns_none(self) -> None:
        advisor = TradeAdvisor(AdvisorConfig())
        candidate = make_candidate(entry=24760.0, stop=24000.0, targets=(26000.0,))
        signal = Signal(
            candidate=candidate,
            score=80.0,
            classification=SignalClassification.HIGH_QUALITY,
            accepted=True,
            timestamp=NOW,
        )
        assert (
            advisor.build_brief(
                signal=signal,
                risk=make_risk(),
                chain=make_chain(),
                metrics=make_metrics(),
                generated_at=NOW,
            )
            is None
        )

    def test_strike_offset_selects_next_otm(self) -> None:
        advisor = TradeAdvisor(AdvisorConfig(strike_offset=1))
        brief = advisor.build_brief(
            signal=make_signal(),
            risk=make_risk(),
            chain=make_chain(),
            metrics=make_metrics(),
            generated_at=NOW,
        )
        assert brief is not None
        assert brief.contract is not None
        assert brief.contract.strike == 24800.0

    def test_wait_brief_is_explicit(self) -> None:
        advisor = TradeAdvisor(AdvisorConfig())
        brief = advisor.build_wait(
            underlying_symbol="NIFTY",
            reason="No strategy setup in the current regime.",
            spot=24752.0,
            regime=make_regime(),
            generated_at=NOW,
        )
        assert brief.action == "WAIT"
        assert brief.waiting_reason == "No strategy setup in the current regime."
        assert brief.is_actionable is False
        assert brief.setup_key == "NIFTY|WAIT"

    def test_should_notify_dedupes_within_cooldown(self) -> None:
        advisor = TradeAdvisor(AdvisorConfig(telegram_dedupe_minutes=15))
        brief = advisor.build_brief(
            signal=make_signal(),
            risk=make_risk(),
            chain=make_chain(),
            metrics=make_metrics(),
            generated_at=NOW,
        )
        assert advisor.should_notify(brief, now=NOW) is True
        assert advisor.should_notify(brief, now=NOW + timedelta(minutes=5)) is False
        assert advisor.should_notify(brief, now=NOW + timedelta(minutes=16)) is True

    def test_should_notify_never_fires_for_wait(self) -> None:
        advisor = TradeAdvisor(AdvisorConfig())
        wait_brief = advisor.build_wait(
            underlying_symbol="NIFTY", reason="x", generated_at=NOW
        )
        assert advisor.should_notify(wait_brief, now=NOW) is False


class TestBriefPersistence:
    def test_current_doc_updates_and_history_dedupes(self) -> None:
        store = MarketStore(FirestoreConfig())
        advisor = TradeAdvisor(AdvisorConfig())

        brief = advisor.build_brief(
            signal=make_signal(),
            risk=make_risk(),
            chain=make_chain(),
            metrics=make_metrics(),
            generated_at=NOW,
        )
        assert brief is not None
        assert store.persist_trade_brief(brief) is True

        loaded = store.load_current_trade_brief("NIFTY")
        assert loaded is not None
        assert loaded.contract is not None
        assert loaded.contract.tradingsymbol == "NIFTY 24750CE"
        # current_<symbol> + one history row for the fresh setup
        assert store.trade_briefs.count() == 2

        # Same actionable setup one minute later: current refreshes, no new history.
        again = advisor.build_brief(
            signal=make_signal(),
            risk=make_risk(),
            chain=make_chain(),
            metrics=make_metrics(),
            generated_at=NOW + timedelta(minutes=1),
        )
        assert again is not None
        store.persist_trade_brief(again)
        assert store.trade_briefs.count() == 2

        # WAIT briefs refresh current but are never historised.
        wait_brief = advisor.build_wait(
            underlying_symbol="NIFTY",
            reason="Stand down.",
            generated_at=NOW + timedelta(minutes=2),
        )
        store.persist_trade_brief(wait_brief)
        assert store.trade_briefs.count() == 2
        assert store.load_current_trade_brief("NIFTY").action == "WAIT"