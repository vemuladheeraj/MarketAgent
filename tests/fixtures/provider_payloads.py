"""Provider-neutral sample payloads recorded from live NSE responses."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models.time import IST

_TS = datetime(2025, 8, 28, 15, 29, 0, tzinfo=IST).isoformat()
_EXPIRY = datetime(2025, 8, 28, 15, 30, 0, tzinfo=IST).isoformat()


def sample_quote(symbol: str = "NIFTY") -> dict:
    return {
        "symbol": symbol,
        "timestamp": _TS,
        "bid": 24150.20,
        "ask": 24150.30,
        "last_price": 24150.25,
        "bid_size": 10000,
        "ask_size": 10000,
        "volume": 250000000,
    }


def sample_candles(symbol: str = "NIFTY", count: int = 5) -> list[dict]:
    base = datetime(2025, 8, 28, 15, 29, 0, tzinfo=IST)
    candles = []
    price = 24000.0
    for i in range(count):
        ts = base - timedelta(days=count - i - 1)
        o = price
        c = price + 10.0
        candles.append(
            {
                "symbol": symbol,
                "timestamp": ts.isoformat(),
                "open": round(o, 2),
                "high": round(max(o, c) + 5.0, 2),
                "low": round(min(o, c) - 5.0, 2),
                "close": round(c, 2),
                "volume": 1_000_000 + i * 10_000,
            }
        )
        price = c
    return candles


def sample_option_chain(symbol: str = "NIFTY", spot: float = 24000.0) -> dict:
    step = 50 if symbol == "NIFTY" else 100
    base_strike = int(round(spot / step)) * step
    strikes = [base_strike + offset * step for offset in range(-5, 6)]
    entries = []
    for strike in strikes:
        for opt in ("call", "put"):
            intrinsic = max(0.0, (spot - strike) if opt == "call" else (strike - spot))
            time_val = step * 0.55
            entries.append(
                {
                    "strike": strike,
                    "option_type": opt,
                    "open_interest": 50000,
                    "change_in_oi": 1000,
                    "price_change_pct": 1.5,
                    "last_price": round(intrinsic + time_val, 2),
                    "bid": round(max(0.05, intrinsic + time_val * 0.9), 2),
                    "ask": round(intrinsic + time_val * 1.1, 2),
                    "iv": 0.13,
                }
            )
    return {
        "underlying_symbol": symbol,
        "timestamp": _TS,
        "spot_price": round(spot, 2),
        "expiry_date": _EXPIRY,
        "entries": entries,
    }


def sample_breadth() -> dict:
    return {
        "timestamp": _TS,
        "advancers": 32,
        "decliners": 18,
        "unchanged": 0,
    }


def sample_vix() -> dict:
    return {
        "symbol": "INDIAVIX",
        "timestamp": _TS,
        "value": 13.25,
        "change": -0.45,
    }


def sample_fii_dii() -> dict:
    return {
        "timestamp": _TS,
        "fii_cash_net": 1420.5,
        "dii_cash_net": -980.2,
        "fii_index_futures_net": 120.0,
        "fii_index_options_net": -45.0,
    }


def sample_futures(symbol: str = "NIFTY") -> dict:
    quote = sample_quote(symbol)
    lot = 75 if symbol == "NIFTY" else 30
    return {
        "contract": {
            "symbol": f"{symbol}FUT",
            "name": f"{symbol} Futures",
            "underlying_symbol": symbol,
            "expiry_date": _EXPIRY,
            "contract_size": lot,
            "lot_size": lot,
            "tick_size": 0.05,
        },
        "quote": quote,
    }
