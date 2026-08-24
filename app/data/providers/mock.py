"""Deterministic mock market-data provider for development and testing.

IMPORTANT: this provider synthesises data with a fixed random seed and a
fixed reference date so that every run and every test is reproducible. It is
explicitly labelled as *mock* — it must never be mistaken for real market
data, and in production the application is configured with a live provider.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import numpy as np

from app.data.providers.base import MarketDataProvider, ProviderError
from app.models.time import IST

#: Reference date used so results are deterministic (a trading Friday).
DEFAULT_REFERENCE_DATE = date(2025, 6, 27)

SESSION_CLOSE = time(15, 29)

#: (symbol, base_price, strike_step) for watchlist instruments.
INSTRUMENTS = {
    "NIFTY": (24000.0, 50),
    "BANKNIFTY": (52000.0, 100),
}


class MockMarketDataProvider(MarketDataProvider):
    """Deterministic synthetic provider.

    Parameters
    ----------
    seed:
        Any seed makes the sequence deterministic; the default is fixed so
        tests are stable across machines.
    reference_date:
        The last "today" of the synthetic series. Default keeps tests
        stable across time.
    base_prices:
        Optional per-symbol base price override.
    """

    name = "mock_replay"

    def __init__(
        self,
        seed: int = 123,
        reference_date: date | None = None,
        base_prices: dict[str, float] | None = None,
    ) -> None:
        self._rng = np.random.default_rng(seed)
        self._reference = reference_date or DEFAULT_REFERENCE_DATE
        self._base: dict[str, float] = {}
        for sym, (price, step) in INSTRUMENTS.items():
            self._base[sym] = (base_prices or {}).get(sym, price), step
        self._candle_cache: dict[tuple[str, str], list[dict]] = {}

    # -- helpers ------------------------------------------------------
    def _ref_dt(self, hour: int = 15, minute: int = 29) -> datetime:
        return datetime.combine(self._reference, time(hour, minute), tzinfo=IST)

    def _bounded(self) -> float:
        """Deterministic float in [0,1)."""
        return float(self._rng.random())

    def _price_series(self, symbol: str, n: int) -> np.ndarray:
        spot = self._base[symbol][0]
        shocks = self._rng.normal(0.0002, 0.011, size=n)
        path = spot * np.exp(np.cumsum(shocks))
        return np.clip(path, spot * 0.75, spot * 1.25)

    def _candles(self, symbol: str, lookback_days: int = 40, timeframe: str = "1d"):
        key = (symbol, timeframe)
        if key in self._candle_cache and len(self._candle_cache[key]) >= lookback_days:
            return self._candle_cache[key][:lookback_days]
        n = max(lookback_days, 60)
        path = self._price_series(symbol, n)
        dates = [self._ref_dt() - timedelta(days=d) for d in range(n)][::-1]
        days = []
        for i, ts in enumerate(dates):
            o = float(path[i])
            c = float(path[i + 1]) if i + 1 < n else float(path[i])
            v = int(1_000_000 * (1.5 + self._bounded()))
            hi = max(o, c) * (1 + abs(self._bounded()) * 0.004 + 0.0005)
            lo = min(o, c) * (1 - abs(self._bounded()) * 0.004 - 0.0005)
            days.append(
                {
                    "symbol": symbol,
                    "timestamp": ts.isoformat(),
                    "open": round(o, 2),
                    "high": round(hi, 2),
                    "low": round(lo, 2),
                    "close": round(c, 2),
                    "volume": v,
                }
            )
        self._candle_cache[key] = days
        return days[:lookback_days]
# -- interface -----------------------------------------------------
    def get_quote(self, symbol: str) -> dict:
        symbol = symbol.upper()
        self._check(symbol)
        candles = self._candles(symbol, 1)
        last_close = candles[-1]["close"]
        spread = self._bounded() * 0.004
        bid = last_close * (1 - spread / 2)
        ask = last_close * (1 + spread / 2)
        return {
            "symbol": symbol,
            "timestamp": self._ref_dt().isoformat(),
            "bid": round(bid, 2),
            "ask": round(ask, 2),
            "last_price": round(last_close, 2),
            "bid_size": int(10_000 * (1 + self._bounded())),
            "ask_size": int(10_000 * (1 + self._bounded())),
            "volume": candles[-1]["volume"],
        }

    def get_candles(
        self, symbol: str, lookback_days: int = 30, timeframe: str = "1d"
    ) -> list[dict]:
        symbol = symbol.upper()
        self._check(symbol)
        if lookback_days < 1:
            raise ProviderError("lookback_days must be >= 1")
        return self._candles(symbol, lookback_days, timeframe)

    def get_option_chain(
        self, symbol: str, expiry_date: datetime | date | None = None
    ) -> dict:
        symbol = symbol.upper()
        self._check(symbol)
        spot, step = self._base[symbol][0], self._base[symbol][1]
        exp = expiry_date or (self._ref_dt() + timedelta(days=7))
        if isinstance(exp, date) and not isinstance(exp, datetime):
            exp = datetime.combine(exp, time(15, 30), tzinfo=IST)
        elif isinstance(exp, datetime) and exp.tzinfo is None:
            exp = exp.replace(tzinfo=IST)
        elif isinstance(exp, datetime):
            exp = exp.astimezone(IST)

        base_strike = int(round(spot / step)) * step
        strikes = [base_strike + offset * step for offset in range(-5, 6)]

        entries = []
        for s in strikes:
            for opt in ("call", "put"):
                intrinsic = max(0.0, (spot - s) if opt == "call" else (s - spot))
                time_val = (0.15 + self._bounded()) * step * 0.55
                entries.append(
                    {
                        "strike": s,
                        "option_type": opt,
                        "open_interest": int(5000 + self._bounded() * 95000),
                        "change_in_oi": int((self._bounded() - 0.5) * 8000),
                        "price_change_pct": round((self._bounded() - 0.5) * 6.0, 3),
                        "last_price": round(intrinsic + time_val, 2),
                        "bid": round(max(0.05, intrinsic + time_val * 0.9), 2),
                        "ask": round(intrinsic + time_val * 1.1, 2),
                        "iv": round(0.10 + self._bounded() * 0.35, 4),
                    }
                )
        return {
            "underlying_symbol": symbol,
            "timestamp": self._ref_dt().isoformat(),
            "spot_price": round(spot, 2),
            "expiry_date": exp.isoformat(),
            "entries": entries,
        }

    def get_futures_data(self, symbol: str) -> dict:
        symbol = symbol.upper()
        self._check(symbol)
        quote = self.get_quote(symbol)
        lot = 75 if symbol == "NIFTY" else 40
        return {
            "contract": {
                "symbol": f"{symbol}FUT",
                "name": f"{symbol} Futures",
                "underlying_symbol": symbol,
                "expiry_date": (self._ref_dt() + timedelta(days=7)).isoformat(),
                "contract_size": lot,
                "lot_size": lot,
                "tick_size": 0.05,
            },
            "quote": quote,
        }

    def get_market_breadth(self) -> dict:
        return {
            "timestamp": self._ref_dt().isoformat(),
            "advancers": int(900 + self._bounded() * 900),
            "decliners": int(500 + self._bounded() * 700),
            "unchanged": int(50 + self._bounded() * 100),
        }

    def get_vix(self) -> dict:
        return {
            "symbol": "INDIAVIX",
            "timestamp": self._ref_dt().isoformat(),
            "value": round(11.0 + self._bounded() * 8.0, 2),
            "change": round((self._bounded() - 0.5) * 1.2, 2),
        }

    def get_fii_dii_data(self) -> dict:
        return {
            "timestamp": self._ref_dt().isoformat(),
            "fii_cash_net": round((self._bounded() - 0.45) * 1500, 2),
            "dii_cash_net": round((self._bounded() - 0.55) * 1200, 2),
            "fii_index_futures_net": round((self._bounded() - 0.5) * 800, 2),
            "fii_index_options_net": round((self._bounded() - 0.5) * 400, 2),
        }

    def _check(self, symbol: str) -> None:
        if symbol not in INSTRUMENTS:
            raise ProviderError(
                f"mock provider does not know instrument {symbol!r}; "
                f"known: {list(INSTRUMENTS)}"
            )
