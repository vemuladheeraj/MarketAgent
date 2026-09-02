from __future__ import annotations

from app.data.normalizers.us_options import normalize_us_option_chain


def test_normalize_us_option_chain_handles_yfinance_payload():
    payload = {
        "underlying_symbol": "NVDA",
        "timestamp": "2026-09-01T14:30:00Z",
        "spot_price": 123.45,
        "expiry_date": "2026-09-05",
        "entries": [
            {
                "strike": 120.0,
                "option_type": "CALL",
                "last_price": 6.2,
                "bid": 6.15,
                "ask": 6.25,
                "open_interest": 1300,
                "change_in_oi": 150,
                "iv": 0.42,
                "delta": 0.61,
                "gamma": 0.06,
                "theta": -0.08,
                "vega": 0.17,
            },
            {
                "strike": 125.0,
                "option_type": "PUT",
                "last_price": 7.1,
                "bid": 7.0,
                "ask": 7.2,
                "open_interest": 1100,
                "change_in_oi": -80,
                "iv": 0.38,
                "delta": -0.52,
                "gamma": 0.05,
                "theta": -0.07,
                "vega": 0.15,
            },
        ],
    }

    chain = normalize_us_option_chain(payload)
    assert chain.underlying_symbol == "NVDA"
    assert len(chain.entries) == 2
    assert chain.entries[0].option_type.value == "call"
    assert chain.entries[0].iv is not None
