"""Open-interest and option-structure analysis.

Deterministic rules over a normalized option chain. OI is treated as one
factor among many — OI direction alone never predicts price direction.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np

from app.analysis.options.black_scholes import greeks, implied_volatility
from app.models.enums import Moneyness, OptionType, PositionBuild
from app.models.options import OptionChainEntry, OptionChainSnapshot
from app.models.options_analysis import (
    OISummary,
    OptionGreeks,
    OptionMetrics,
    StrikePositionAnalysis,
)

#: strikes within 0.5% of spot are considered ATM
ATM_TOLERANCE_PCT = 0.005


def classify_position(
    option_type: OptionType, change_in_oi: float, price_change_pct: float
) -> PositionBuild:
    """Classify OI + *option premium* change into a position-build type.

    The same premium convention is used for calls and puts. This is not a
    directional forecast of the underlying.
    """
    del option_type  # premium convention is identical for both sides
    if abs(change_in_oi) < 1:
        return PositionBuild.OI_UNCHANGED
    oi_up = change_in_oi > 0
    price_up = price_change_pct > 0
    if oi_up and price_up:
        return PositionBuild.LONG_BUILDUP
    if oi_up and not price_up:
        return PositionBuild.SHORT_BUILDUP
    if not oi_up and price_up:
        return PositionBuild.SHORT_COVERING
    return PositionBuild.LONG_UNWINDING


def moneyness(spot: float, strike: float, option_type: OptionType) -> Moneyness:
    pct = abs(strike - spot) / spot
    if pct <= ATM_TOLERANCE_PCT:
        return Moneyness.ATM
    intrinsic_positive = (option_type == OptionType.CALL and strike < spot) or (
        option_type == OptionType.PUT and strike > spot
    )
    return Moneyness.ITM if intrinsic_positive else Moneyness.OTM


class OptionsAnalyzer:
    """Computes OptionMetrics from an OptionChainSnapshot."""

    def __init__(self, risk_free_rate: float = 0.065) -> None:
        self.risk_free_rate = risk_free_rate

    def analyze(
        self,
        chain: OptionChainSnapshot,
        prev_metrics: OptionMetrics | None = None,
    ) -> OptionMetrics:
        spot = chain.spot_price
        t_years = self._years_to_expiry(chain.timestamp, chain.expiry_date)
        if t_years <= 0:
            raise ValueError("expiry must be after snapshot timestamp")

        oi = self._oi_summary(chain, spot)
        metrics = OptionMetrics(
            underlying_symbol=chain.underlying_symbol,
            timestamp=chain.timestamp,
            expiry_date=chain.expiry_date,
            spot_price=spot,
            oi=oi,
        )
        metrics.atm_strike = self._nearest_strike(chain, spot)

        iv_values: list[float] = []
        for entry in chain.entries:
            entry_key = self._entry_key(entry)
            entry_moneyness = moneyness(spot, entry.strike, entry.option_type)
            price_change_pct = entry.price_change_pct or 0.0
            build = classify_position(
                entry.option_type,
                entry.change_in_oi or 0,
                price_change_pct,
            )
            metrics.strike_analysis[entry_key] = StrikePositionAnalysis(
                strike=entry.strike,
                option_type=entry.option_type,
                moneyness=entry_moneyness,
                change_in_oi=entry.change_in_oi or 0,
                price_change_pct=price_change_pct,
                build=build,
                description=build.value,
            )

            sigma = entry.iv
            if sigma is None and entry.last_price is not None:
                sigma = implied_volatility(
                    spot, entry.strike, t_years, entry.last_price,
                    self.risk_free_rate, entry.option_type,
                )
            g = OptionGreeks(iv=sigma)
            if sigma is not None and 0 < sigma:
                try:
                    gs = greeks(
                        spot, entry.strike, t_years, sigma,
                        self.risk_free_rate, entry.option_type,
                    )
                    g.delta, g.gamma = gs["delta"], gs["gamma"]
                    g.theta, g.vega = gs["theta"], gs["vega"]
                except ValueError:
                    pass
            metrics.greeks[entry_key] = g
            if sigma is not None:
                iv_values.append(sigma)

        if iv_values:
            oi.avg_iv = float(np.mean(iv_values))

        metrics.near_strikes = self._near_strikes(chain, spot)

        if (
            prev_metrics is not None
            and prev_metrics.oi.avg_iv is not None
            and oi.avg_iv is not None
        ):
            delta_iv = oi.avg_iv - prev_metrics.oi.avg_iv
            metrics.iv_expansion = delta_iv > 0.005
            metrics.iv_contraction = delta_iv < -0.005

        return metrics

    @staticmethod
    def _years_to_expiry(ts: datetime, expiry: datetime) -> float:
        if expiry <= ts:
            return 0.0
        return (expiry - ts).total_seconds() / (365.0 * 86400.0)

    @staticmethod
    def _entry_key(entry: OptionChainEntry) -> str:
        side = "CE" if entry.is_call else "PE"
        return f"{entry.strike:g}{side}"

    @staticmethod
    def _nearest_strike(chain: OptionChainSnapshot, spot: float) -> float | None:
        if not chain.entries:
            return None
        return min(chain.entries, key=lambda e: abs(e.strike - spot)).strike

    @staticmethod
    def _near_strikes(
        chain: OptionChainSnapshot,
        spot: float,
        count_each_side: int = 2,
    ) -> list[float]:
        strikes = sorted({e.strike for e in chain.entries})
        if not strikes:
            return []
        center = min(range(len(strikes)), key=lambda idx: abs(strikes[idx] - spot))
        start = max(0, center - count_each_side)
        end = min(len(strikes), center + count_each_side + 1)
        return strikes[start:end]

    def _oi_summary(self, chain: OptionChainSnapshot, spot: float) -> OISummary:
        calls = [e for e in chain.entries if e.is_call]
        puts = [e for e in chain.entries if e.is_put]

        total_call_oi = sum(e.open_interest for e in calls)
        total_put_oi = sum(e.open_interest for e in puts)
        pcr = total_put_oi / total_call_oi if total_call_oi else None

        max_call = max(calls, key=lambda e: e.open_interest) if calls else None
        max_put = max(puts, key=lambda e: e.open_interest) if puts else None

        call_resistance = None
        if calls:
            above = [e for e in calls if e.strike > spot]
            if above:
                call_resistance = max(above, key=lambda e: e.open_interest).strike
        put_support = None
        if puts:
            below = [e for e in puts if e.strike < spot]
            if below:
                put_support = max(below, key=lambda e: e.open_interest).strike

        all_iv = [e.iv for e in chain.entries if e.iv is not None]
        avg_iv = float(np.mean(all_iv)) if all_iv else None

        return OISummary(
            total_call_oi=total_call_oi,
            total_put_oi=total_put_oi,
            pcr=pcr,
            max_call_oi_strike=max_call.strike if max_call else None,
            max_put_oi_strike=max_put.strike if max_put else None,
            call_concentration=(
                max_call.open_interest / total_call_oi
                if max_call and total_call_oi
                else None
            ),
            put_concentration=(
                max_put.open_interest / total_put_oi
                if max_put and total_put_oi
                else None
            ),
            call_resistance=call_resistance,
            put_support=put_support,
            change_in_oi_total_calls=sum(e.change_in_oi or 0 for e in calls),
            change_in_oi_total_puts=sum(e.change_in_oi or 0 for e in puts),
            avg_iv=avg_iv,
        )
