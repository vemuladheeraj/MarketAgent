"""Tests for the Black-Scholes engine, OI analysis and OptionsAnalyzer."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.analysis.options import (
    OptionsAnalyzer,
    bsm_price,
    classify_position,
    greeks,
    implied_volatility,
    moneyness,
)
from app.data.normalizers import MarketDataNormalizer
from app.data.providers import MockMarketDataProvider
from app.models import (
    Moneyness,
    OptionType,
    PositionBuild,
)
from app.models.time import IST

NORMALIZER = MarketDataNormalizer()
ANALYZER = OptionsAnalyzer(risk_free_rate=0.065)


def _chain(spot: float = 24000.0):
    return NORMALIZER.normalize_chain(MockMarketDataProvider().get_option_chain("NIFTY"))


class TestBlackScholes:
    def test_price_symmetry_put_call_parity(self):
        # call - put = S - K*e^{-rT} (put-call parity)
        S, K, T, sigma, r = 100.0, 100.0, 1.0, 0.20, 0.05
        call = bsm_price(S, K, T, sigma, r, Call=OptionType.CALL)
        put = bsm_price(S, K, T, sigma, r, Call=OptionType.PUT)
        parity = call - put
        import math

        expected = S - K * math.exp(-r * T)
        assert parity == pytest.approx(expected, abs=1e-6)

    def test_atm_call_price_approx(self):
        # ATM call approx 0.4*S*sigma*sqrt(T) for small vol
        import math
        S, K, T, sigma = 100.0, 100.0, 0.25, 0.2
        price = bsm_price(S, K, T, sigma)
        approx = 0.4 * S * sigma * math.sqrt(T)
        assert price == pytest.approx(approx, rel=0.15)

    def test_delta_call_between_0_and_1(self):
        g = greeks(100.0, 100.0, 1.0, 0.2, 0.05, OptionType.CALL)
        assert 0 < g["delta"] < 1

    def test_delta_put_between_minus_1_and_0(self):
        g = greeks(100.0, 100.0, 1.0, 0.2, 0.05, OptionType.PUT)
        assert -1 < g["delta"] < 0

    def test_gamma_positive(self):
        g = greeks(100.0, 100.0, 1.0, 0.2, 0.05, OptionType.CALL)
        assert g["gamma"] > 0

    def test_theta_daily_negative_long_atm(self):
        g = greeks(100.0, 100.0, 0.1, 0.2, 0.05, OptionType.CALL)
        assert g["theta"] < 0

    def test_iv_recovers_sigma(self):
        S, K, T, sigma = 100.0, 105.0, 0.5, 0.25
        price = bsm_price(S, K, T, sigma)
        iv = implied_volatility(S, K, T, price)
        assert iv == pytest.approx(sigma, abs=1e-4)

    def test_iv_none_below_intrinsic(self):
        iv = implied_volatility(100.0, 90.0, 1.0, 1.0)  # below intrinsic 10
        assert iv is None


class TestClassifyAndMoneyness:
    def test_call_long_buildup(self):
        assert classify_position(OptionType.CALL, +100, +1.0) == PositionBuild.LONG_BUILDUP

    def test_call_short_buildup(self):
        assert classify_position(OptionType.CALL, +100, -1.0) == PositionBuild.SHORT_BUILDUP

    def test_put_long_buildup(self):
        assert classify_position(OptionType.PUT, +100, -1.0) == PositionBuild.LONG_BUILDUP

    def test_put_shorted_covering(self):
        assert classify_position(OptionType.PUT, -100, +1.0) == PositionBuild.SHORT_COVERING

    def test_oi_unchanged(self):
        assert classify_position(OptionType.CALL, 0, 0.0) == PositionBuild.OI_UNCHANGED

    def test_moneyness_atm(self):
        assert moneyness(100.0, 100.2, OptionType.CALL) == MoneyType.ATM.value
        # compare against enum directly
        from app.models.enums import Moneyness as MoneynessEnum

        assert moneyness(100.0, 99.9, OptionType.CALL) == MoneynessEnum.ATM

    def test_moneyness_itm_otm(self):
        assert moneyness(100.0, 90.0, OptionType.CALL) == Moneyness.ITM
        assert moneyness(100.0, 110.0, OptionType.CALL) == Moneyness.OTM
        assert moneyness(100.0, 110.0, OptionType.PUT) == Moneyness.ITM
        assert moneyness(100.0, 90.0, OptionType.PUT) == Moneyness.OTM


class TestAnalyzer:
    def test_metrics_produced(self):
        chain = _norm(24000.0)
        metrics = ANALYZER.analyze(chain)
        assert metrics.underlying_symbol == "NIFTY"
        assert metrics.spot_price == pytest.approx(24000.0, rel=0.5)
        assert metrics.oi.total_call_oi > 0
        assert metrics.oi.total_put_oi > 0
        assert metrics.oi.pcr is not None
        assert metrics.atm_strike is not None
        assert len(metrics.greeks) == 22
        first_greek = next(iter(metrics.greeks.values()))
        assert first_greek.iv is None or 0 < first_greek.iv

    def test_call_resistance_and_put_support(self):
        chain = _chain(24000.0)
        metrics = ANALYZER.analyze(chain)
        if metrics.oi.call_resistance is not None:
            assert metrics.oi.call_resistance > chain.spot_price
        if metrics.oi.put_support is not None:
            assert metrics.oi.put_support < chain.spot_price