"""Unit tests for the Direct NSE India Web Market Data Provider."""

from __future__ import annotations

import httpx
import pytest

from app.config.settings import ProviderConfig
from app.data.normalizers.normalizer import MarketDataNormalizer
from app.data.providers.base import ProviderError
from app.data.providers.factory import create_provider
from app.data.providers.nse import NSEMarketDataProvider


# -- Fixture mock responses ----------------------------------------------------

MOCK_ALL_INDICES_RESP = {
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

MOCK_OPTION_CHAIN_RESP = {
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
                    "impliedVolatility": 12.5,
                },
                "PE": {
                    "strikePrice": 24100,
                    "expiryDate": "28-Aug-2025",
                    "openInterest": 60000,
                    "changeinOpenInterest": -1200,
                    "pChange": -6.2,
                    "lastPrice": 75.0,
                    "bidprice": 74.9,
                    "askPrice": 75.1,
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


def mock_transport_handler(request: httpx.Request) -> httpx.Response:
    url_str = str(request.url)
    if "allIndices" in url_str:
        return httpx.Response(200, json=MOCK_ALL_INDICES_RESP)
    if "option-chain-indices" in url_str:
        return httpx.Response(200, json=MOCK_OPTION_CHAIN_RESP)
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


@pytest.fixture
def mock_nse_provider() -> NSEMarketDataProvider:
    transport = httpx.MockTransport(mock_transport_handler)
    client = httpx.Client(transport=transport)
    return NSEMarketDataProvider(client=client, cache_ttl_seconds=0.0)


# -- Test Cases ---------------------------------------------------------------

def test_factory_creates_nse_provider() -> None:
    config = ProviderConfig(name="nse")
    provider = create_provider(config)
    assert isinstance(provider, NSEMarketDataProvider)
    assert provider.name == "nse"


def test_get_quote(mock_nse_provider: NSEMarketDataProvider) -> None:
    quote = mock_nse_provider.get_quote("NIFTY")
    assert quote["symbol"] == "NIFTY"
    assert quote["last_price"] == 24150.25
    assert quote["open"] == 24050.0
    assert quote["volume"] == 250000000
    assert quote["bid"] <= quote["ask"]

    # Test normalization
    normalizer = MarketDataNormalizer()
    normalized = normalizer.normalize_quote(quote, "NIFTY")
    assert normalized.last_price == 24150.25
    assert normalized.volume == 250000000


def test_get_vix(mock_nse_provider: NSEMarketDataProvider) -> None:
    vix = mock_nse_provider.get_vix()
    assert vix["symbol"] == "INDIAVIX"
    assert vix["value"] == 13.25
    assert vix["change"] == -0.45


def test_get_market_breadth(mock_nse_provider: NSEMarketDataProvider) -> None:
    breadth = mock_nse_provider.get_market_breadth()
    assert breadth["advancers"] == 32
    assert breadth["decliners"] == 18
    assert breadth["unchanged"] == 0

    normalizer = MarketDataNormalizer()
    normalized = normalizer.normalize_breadth(breadth)
    assert normalized.advancers == 32
    assert normalized.decliners == 18


def test_get_option_chain(mock_nse_provider: NSEMarketDataProvider) -> None:
    chain = mock_nse_provider.get_option_chain("NIFTY")
    assert chain["underlying_symbol"] == "NIFTY"
    assert chain["spot_price"] == 24150.25
    assert len(chain["entries"]) == 4  # 2 strikes * (CE + PE)

    normalizer = MarketDataNormalizer()
    normalized = normalizer.normalize_chain(chain)
    assert normalized.spot_price == 24150.25
    assert len(normalized.entries) == 4
    assert len(normalized.calls()) == 2
    assert len(normalized.puts()) == 2
    assert normalized.pcr is not None


def test_get_candles(mock_nse_provider: NSEMarketDataProvider) -> None:
    candles = mock_nse_provider.get_candles("NIFTY", lookback_days=2)
    assert len(candles) == 2
    assert candles[-1]["close"] == 24150.0

    normalizer = MarketDataNormalizer()
    normalized = normalizer.normalize_candle_list(candles)
    assert len(normalized) == 2
    assert normalized[-1].close_price == 24150.0


def test_get_futures_data(mock_nse_provider: NSEMarketDataProvider) -> None:
    fut = mock_nse_provider.get_futures_data("NIFTY")
    assert fut["contract"]["symbol"] == "NIFTYFUT"
    assert fut["quote"]["last_price"] == 24150.25


def test_missing_symbol_error(mock_nse_provider: NSEMarketDataProvider) -> None:
    with pytest.raises(ProviderError, match="not found in NSE allIndices"):
        mock_nse_provider.get_quote("NON_EXISTENT_SYMBOL")


def test_http_error_handling() -> None:
    def error_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(error_transport)
    client = httpx.Client(transport=transport)
    provider = NSEMarketDataProvider(client=client)

    with pytest.raises(ProviderError, match="returned HTTP 500"):
        provider.get_quote("NIFTY")
