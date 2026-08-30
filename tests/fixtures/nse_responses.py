"""Recorded NSE API response payloads for isolated provider unit tests."""

from __future__ import annotations

import httpx

SAMPLE_ALL_INDICES_RESP = {
    "data": [
        {
            "key": "BROAD MARKET INDICES",
            "index": "NIFTY 50",
            "indexSymbol": "NIFTY 50",
            "last": 24150.25,
            "variation": 125.4,
            "percentChange": 0.52,
            "open": 24050.0,
            "high": 24180.0,
            "low": 24020.0,
            "previousClose": 24024.85,
            "advances": "32",
            "declines": "18",
            "unchanged": "0",
            "date": "28-Aug-2025 15:30:00",
            "totalTradedVolume": 250000000,
        },
        {
            "key": "SECTORAL INDICES",
            "index": "NIFTY BANK",
            "indexSymbol": "NIFTY BANK",
            "last": 52100.0,
            "variation": -50.0,
            "percentChange": -0.1,
            "open": 52150.0,
            "high": 52300.0,
            "low": 52000.0,
            "previousClose": 52150.0,
            "advances": "8",
            "declines": "4",
            "unchanged": "0",
            "date": "28-Aug-2025 15:30:00",
            "totalTradedVolume": 100000000,
        },
        {
            "key": "OTHER",
            "index": "INDIA VIX",
            "indexSymbol": "INDIA VIX",
            "last": 13.25,
            "variation": -0.45,
            "percentChange": -3.28,
            "date": "28-Aug-2025 15:30:00",
        },
    ]
}

SAMPLE_OPTION_CHAIN_RESP = {
    "records": {
        "expiryDates": ["28-Aug-2025", "04-Sep-2025"],
        "data": [
            {
                "strikePrice": 24100,
                "expiryDate": "28-Aug-2025",
                "CE": {
                    "strikePrice": 24100,
                    "expiryDate": "28-Aug-2025",
                    "openInterest": 45000,
                    "changeinOpenInterest": 3500,
                    "pChange": 4.5,
                    "lastPrice": 120.5,
                    "bidprice": 120.4,
                    "askPrice": 120.6,
                    "impliedVolatility": 13.2,
                },
                "PE": {
                    "strikePrice": 24100,
                    "expiryDate": "28-Aug-2025",
                    "openInterest": 60000,
                    "changeinOpenInterest": -2000,
                    "pChange": -1.5,
                    "lastPrice": 85.0,
                    "bidprice": 84.8,
                    "askPrice": 85.2,
                    "impliedVolatility": 13.0,
                },
            },
            {
                "strikePrice": 24200,
                "expiryDate": "28-Aug-2025",
                "CE": {
                    "strikePrice": 24200,
                    "expiryDate": "28-Aug-2025",
                    "openInterest": 80000,
                    "changeinOpenInterest": 8000,
                    "pChange": -2.0,
                    "lastPrice": 65.0,
                    "bidprice": 64.8,
                    "askPrice": 65.2,
                    "impliedVolatility": 12.8,
                },
                "PE": {
                    "strikePrice": 24200,
                    "expiryDate": "28-Aug-2025",
                    "openInterest": 30000,
                    "changeinOpenInterest": 1500,
                    "pChange": 8.0,
                    "lastPrice": 140.0,
                    "bidprice": 139.8,
                    "askPrice": 140.2,
                    "impliedVolatility": 13.5,
                },
            },
        ],
        "timestamp": "28-Aug-2025 10:30:00",
        "underlyingValue": 24150.25,
    }
}


def nse_transport_handler(request: httpx.Request) -> httpx.Response:
    url_str = str(request.url)
    if "allIndices" in url_str:
        return httpx.Response(200, json=SAMPLE_ALL_INDICES_RESP)
    if "option-chain-contract-info" in url_str:
        return httpx.Response(
            200,
            json={"expiryDates": SAMPLE_OPTION_CHAIN_RESP["records"]["expiryDates"]},
        )
    if "option-chain-v3" in url_str or "option-chain-indices" in url_str:
        return httpx.Response(200, json=SAMPLE_OPTION_CHAIN_RESP)
    if "option-chain" in url_str:
        return httpx.Response(200, text="<html>NSE Option Chain</html>")
    if "finance/chart" in url_str:
        chart_data = {
            "chart": {
                "result": [
                    {
                        "timestamp": [1724835600, 1724922000],
                        "indicators": {
                            "quote": [
                                {
                                    "open": [24000.0, 24100.0],
                                    "high": [24150.0, 24200.0],
                                    "low": [23950.0, 24050.0],
                                    "close": [24100.0, 24150.0],
                                    "volume": [1000000, 1200000],
                                }
                            ]
                        },
                    }
                ]
            }
        }
        return httpx.Response(200, json=chart_data)
    return httpx.Response(404, text="Not Found")
