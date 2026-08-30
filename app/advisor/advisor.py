"""TradeAdvisor: present-moment decision support for a human trader.

The advisor fuses the best accepted signal, risk-engine sizing and the live
option chain into a single :class:`TradeBrief` — the concrete answer to
"what should I do right now?". It never places orders; the human executes.

Deterministic mapping rules
---------------------------
* LONG underlying view  -> buy the nearest-ATM CALL (``strike_offset`` moves
  further out of the money).
* SHORT underlying view -> buy the nearest-ATM PUT.
* Index-level risk/reward distances are translated into premium space with
  the contract delta when available, otherwise with the premium/spot ratio
  as a fallback (flagged as a warning on the brief).
* When the computed premium stop is not positive (premium too small for the
  setup risk) or the chain has no usable contract, no actionable brief is
  produced and the caller emits an explicit WAIT brief instead.
* Telegram re-alerts for the same setup are suppressed for a cooldown window.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.analysis.regime import RegimeAssessment
from app.config.settings import AdvisorConfig
from app.models.advisor import OptionContractRef, TradeBrief
from app.models.enums import DataQuality, Direction, OptionType, SignalClassification
from app.models.options import OptionChainSnapshot
from app.models.options_analysis import OptionMetrics
from app.models.risk import RiskAssessment
from app.models.time import ensure_ist, now_ist
from app.models.trading import Signal


class TradeAdvisor:
    """Builds present-moment :class:`TradeBrief` artifacts from pipeline outputs."""

    def __init__(self, config: AdvisorConfig) -> None:
        self.config = config
        self._last_notified: dict[str, datetime] = {}

    # ------------------------------------------------------------------
    # Actionable briefs
    # ------------------------------------------------------------------

    def build_brief(
        self,
        *,
        signal: Signal,
        risk: RiskAssessment,
        chain: OptionChainSnapshot,
        metrics: OptionMetrics | None = None,
        regime: RegimeAssessment | None = None,
        data_quality: DataQuality = DataQuality.VALID,
        generated_at: datetime | None = None,
    ) -> TradeBrief | None:
        """Build an actionable brief from a risk-approved signal.

        Returns ``None`` when the live chain cannot support a concrete
        contract plan (the caller should emit a WAIT brief).
        """
        candidate = signal.candidate
        now = ensure_ist(generated_at) if generated_at else now_ist()
        option_type = (
            OptionType.CALL if candidate.direction == Direction.LONG else OptionType.PUT
        )
        ref = self._select_contract(chain, option_type, metrics)
        if ref is None or ref.last_price is None or ref.last_price <= 0:
            return None

        premium = ref.last_price
        if ref.delta is not None and abs(ref.delta) > 1e-9:
            scale = abs(ref.delta)
        elif chain.spot_price > 0:
            scale = premium / chain.spot_price
        else:
            return None
        if scale <= 0:
            return None

        premium_risk = candidate.risk_per_unit * scale
        premium_reward = candidate.first_target_reward * scale
        stop = premium - premium_risk
        if stop <= 0:
            # Premium too small to absorb the setup risk at this strike.
            return None
        targets = [
            round(premium + abs(t - candidate.entry) * scale, 2)
            for t in candidate.targets
        ]
        risk_reward = (
            round(premium_reward / premium_risk, 4) if premium_risk > 0 else 0.0
        )

        pos = risk.position_size
        lots = pos.quantity if pos is not None else None
        lot_size = pos.lot_size if pos is not None else 1
        risk_amount = pos.estimated_stop_loss if pos is not None else None
        target_amount = (
            round(risk_amount * risk_reward, 2) if risk_amount is not None else None
        )
        ev = risk.expected_value

        warnings: list[str] = []
        if ref.spread_pct is not None and ref.spread_pct > self.config.max_premium_spread_pct:
            warnings.append(
                f"Premium spread {ref.spread_pct:.1f}% is wide — use limit orders near the mid."
            )
        if ref.delta is None:
            warnings.append(
                "Delta unavailable — premium levels estimated from the premium/spot ratio."
            )
        if data_quality == DataQuality.WARNING:
            warnings.append("Data quality WARNING — verify live prices before bidding.")
        if ref.expiry_date.date() == now.date():
            warnings.append("Contract expires today — gamma/theta risk is elevated.")

        rationale: list[str] = []
        rationale.append(f"{candidate.strategy_name}: {candidate.explanation}")
        if regime is not None:
            rationale.append(
                f"Regime: {regime.regime.value} (confidence {regime.confidence:.0%})."
            )
            if regime.reasons:
                rationale.append(f"Regime driver: {regime.reasons[0]}")
        if metrics is not None:
            oi = metrics.oi
            pcr = f"{oi.pcr:.2f}" if oi.pcr is not None else "n/a"
            cr = f"{oi.call_resistance:.0f}" if oi.call_resistance is not None else "n/a"
            ps = f"{oi.put_support:.0f}" if oi.put_support is not None else "n/a"
            rationale.append(
                f"OI structure: PCR {pcr}; call resistance {cr}; put support {ps}."
            )
        delta_str = f"{ref.delta:.2f}" if ref.delta is not None else "n/a"
        rationale.append(
            f"Contract: {ref.tradingsymbol} — nearest-ATM selection, "
            f"OI {ref.open_interest:,}, delta {delta_str}."
        )
        if pos is not None:
            rationale.append(
                f"Size: {pos.quantity} lots ({pos.units} units) — est. stop-out "
                f"cost ₹{pos.estimated_stop_loss:,.0f} stays within the "
                f"per-trade risk budget."
            )
        if ev is not None:
            rationale.append(
                f"Net EV after costs ≈ ₹{ev.net_expected_value:,.0f} "
                f"({ev.expectancy_r:.2f}R) at win probability {ev.probability:.0%}."
            )
        rationale.append(
            f"Prices move fast — re-verify the live premium before bidding; "
            f"this brief reflects the {now.strftime('%H:%M')} IST cycle."
        )

        return TradeBrief(
            generated_at=now,
            valid_until=now + timedelta(minutes=self.config.validity_minutes),
            action="BUY",
            underlying_symbol=candidate.symbol,
            spot=chain.spot_price,
            strategy_name=candidate.strategy_name,
            underlying_direction=candidate.direction,
            contract=ref,
            entry=round(premium, 2),
            stop_loss=round(stop, 2),
            targets=targets,
            risk_reward=risk_reward,
            lots=lots,
            lot_size=lot_size,
            risk_amount=risk_amount,
            target_amount=target_amount,
            net_expected_value=ev.net_expected_value if ev is not None else None,
            expectancy_r=ev.expectancy_r if ev is not None else None,
            probability=ev.probability if ev is not None else None,
            score=signal.score,
            classification=signal.classification,
            regime=regime.regime.value if regime is not None else "",
            data_quality=data_quality,
            rationale=rationale,
            warnings=warnings,
        )

    def build_wait(
        self,
        *,
        underlying_symbol: str,
        reason: str,
        spot: float | None = None,
        strategy_name: str = "",
        underlying_direction: Direction | None = None,
        regime: RegimeAssessment | None = None,
        score: float | None = None,
        classification: SignalClassification | None = None,
        data_quality: DataQuality = DataQuality.VALID,
        generated_at: datetime | None = None,
    ) -> TradeBrief:
        """Build an explicit WAIT brief — standing aside is a recommendation."""
        now = ensure_ist(generated_at) if generated_at else now_ist()
        rationale: list[str] = []
        if regime is not None:
            rationale.append(
                f"Regime: {regime.regime.value} (confidence {regime.confidence:.0%})."
            )
        rationale.append(reason)
        rationale.append(
            "The agent re-evaluates every cycle — this advice auto-expires at "
            f"{(now + timedelta(minutes=self.config.validity_minutes)).strftime('%H:%M')} IST."
        )
        return TradeBrief(
            generated_at=now,
            valid_until=now + timedelta(minutes=self.config.validity_minutes),
            action="WAIT",
            underlying_symbol=underlying_symbol,
            spot=spot,
            strategy_name=strategy_name,
            underlying_direction=underlying_direction,
            waiting_reason=reason,
            score=score,
            classification=classification,
            regime=regime.regime.value if regime is not None else "",
            data_quality=data_quality,
            rationale=rationale,
        )

    # ------------------------------------------------------------------
    # Contract selection
    # ------------------------------------------------------------------

    def _select_contract(
        self,
        chain: OptionChainSnapshot,
        option_type: OptionType,
        metrics: OptionMetrics | None,
    ) -> OptionContractRef | None:
        """Pick the requested-side strike nearest to spot (offset-able)."""
        side = [e for e in chain.entries if e.option_type == option_type]
        if not side:
            return None
        side.sort(key=lambda e: abs(e.strike - chain.spot_price))
        idx = min(self.config.strike_offset, len(side) - 1)
        entry = side[idx]
        suffix = "CE" if entry.is_call else "PE"
        key = f"{entry.strike:g}{suffix}"

        delta: float | None = None
        if metrics is not None:
            greeks = metrics.greeks.get(key)
            if greeks is not None and greeks.delta is not None:
                delta = greeks.delta
        if delta is None:
            delta = entry.delta

        spread_pct: float | None = None
        if entry.bid is not None and entry.ask is not None and entry.ask > 0:
            mid = (entry.bid + entry.ask) / 2.0
            if mid > 0:
                spread_pct = (entry.ask - entry.bid) / mid * 100.0

        premium = entry.last_price
        if premium is None or premium <= 0:
            if entry.bid is not None and entry.ask is not None:
                premium = (entry.bid + entry.ask) / 2.0

        return OptionContractRef(
            tradingsymbol=f"{chain.underlying_symbol} {entry.strike:g}{suffix}",
            strike=entry.strike,
            option_type=option_type,
            expiry_date=chain.expiry_date,
            last_price=premium if premium is not None and premium > 0 else None,
            bid=entry.bid,
            ask=entry.ask,
            iv=entry.iv,
            delta=delta,
            open_interest=entry.open_interest,
            change_in_oi=entry.change_in_oi,
            spread_pct=spread_pct,
        )

    # ------------------------------------------------------------------
    # Alert dedupe
    # ------------------------------------------------------------------

    def should_notify(self, brief: TradeBrief, *, now: datetime | None = None) -> bool:
        """True when a fresh Telegram alert for this setup should be sent.

        The same setup (symbol/strategy/direction/strike/expiry) is suppressed
        for ``telegram_dedupe_minutes`` after the last alert.
        """
        if not brief.is_actionable:
            return False
        moment = ensure_ist(now) if now is not None else now_ist()
        key = brief.setup_key
        last = self._last_notified.get(key)
        cooldown = timedelta(minutes=self.config.telegram_dedupe_minutes)
        if last is not None and moment - last < cooldown:
            return False
        # Prune stale entries so the map stays small.
        horizon = timedelta(hours=12)
        self._last_notified = {
            k: t for k, t in self._last_notified.items() if moment - t < horizon
        }
        self._last_notified[key] = moment
        return True
