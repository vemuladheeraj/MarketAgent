"""Unit tests for the Direct NSE India Web Market Data Provider."""

from __future__ import annotations

import httpx
import pytest

from app.config.settings import ProviderConfig
from app.data.normalizers.normalizer import MarketDataNormalizer
from app.data.providers.base import ProviderError
from app.data.providers.factory import create_provider
from app.data.providers.nse import NSEMarketDataProvider
from tests.fixtures.nse_responses import nse_transport_handler
from tests.fixtures.nse_stub import make_stub_nse_provider


@pytest.fixture
def stub_nse_provider() -> NSEMarketDataProvider:
    return make_stub_nse_provider()


def test_factory_creates_nse_provider() -> None:
    config = ProviderConfig(name="nse")
    provider = create_provider(config)
    assert isinstance(provider, NSEMarketDataProvider)
    assert provider.name == "nse"


def test_get_quote(stub_nse_provider: NSEMarketDataProvider) -> None:
    quote = stub_nse_provider.get_quote("NIFTY")
    assert quote["symbol"] == "NIFTY"
    assert quote["last_price"] == 24150.25
    assert quote["open"] == 24050.0
    assert quote["volume"] == 250000000
    assert quote["bid"] <= quote["ask"]

    normalizer = MarketDataNormalizer()
    normalized = normalizer.normalize_quote(quote, "NIFTY")
    assert normalized.last_price == 24150.25
    assert normalized.volume == 250000000


def test_get_vix(stub_nse_provider: NSEMarketDataProvider) -> None:
    vix = stub_nse_provider.get_vix()
    assert vix["symbol"] == "INDIAVIX"
    assert vix["value"] == 13.25
    assert vix["change"] == -0.45


def test_get_market_breadth(stub_nse_provider: NSEMarketDataProvider) -> None:
    breadth = stub_nse_provider.get_market_breadth()
    assert breadth["advancers"] == 32
    assert breadth["decliners"] == 18
    assert breadth["unchanged"] == 0

    normalizer = MarketDataNormalizer()
    normalized = normalizer.normalize_breadth(breadth)
    assert normalized.advancers == 32
    assert normalized.decliners == 18


def test_get_option_chain(stub_nse_provider: NSEMarketDataProvider) -> None:
    chain = stub_nse_provider.get_option_chain("NIFTY")
    assert chain["underlying_symbol"] == "NIFTY"
    assert chain["spot_price"] == 24150.25
    assert len(chain["entries"]) == 4

    normalizer = MarketDataNormalizer()
    normalized = normalizer.normalize_chain(chain)
    assert normalized.spot_price == 24150.25
    assert len(normalized.entries) == 4
    assert len(normalized.calls()) == 2
    assert len(normalized.puts()) == 2
    assert normalized.pcr is not None


def test_get_candles(stub_nse_provider: NSEMarketDataProvider) -> None:
    candles = stub_nse_provider.get_candles("NIFTY", lookback_days=2)
    assert len(candles) == 2
    assert candles[-1]["close"] == 24150.0

    normalizer = MarketDataNormalizer()
    normalized = normalizer.normalize_candle_list(candles)
    assert len(normalized) == 2
    assert normalized[-1].close_price == 24150.0


def test_get_futures_data(stub_nse_provider: NSEMarketDataProvider) -> None:
    fut = stub_nse_provider.get_futures_data("NIFTY")
    assert fut["contract"]["symbol"] == "NIFTYFUT"
    assert fut["quote"]["last_price"] == 24150.25


def test_missing_symbol_error(stub_nse_provider: NSEMarketDataProvider) -> None:
    with pytest.raises(ProviderError, match="not found in NSE allIndices"):
        stub_nse_provider.get_quote("NON_EXISTENT_SYMBOL")


def test_http_error_handling() -> None:
    def error_transport(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(error_transport)
    client = httpx.Client(transport=transport)
    provider = NSEMarketDataProvider(client=client)
    provider._stealth_session = None

    with pytest.raises(ProviderError, match="returned HTTP 500"):
        provider.get_quote("NIFTY")
