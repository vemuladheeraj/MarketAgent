"""Stubbed NSE provider backed by recorded API responses."""

from __future__ import annotations

import httpx

from app.data.providers.nse import NSEMarketDataProvider
from tests.fixtures.nse_responses import nse_transport_handler


def make_stub_nse_provider() -> NSEMarketDataProvider:
    transport = httpx.MockTransport(nse_transport_handler)
    client = httpx.Client(transport=transport)
    provider = NSEMarketDataProvider(client=client, cache_ttl_seconds=0.0)
    provider._stealth_session = None
    return provider
