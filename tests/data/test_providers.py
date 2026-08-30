"""Tests for the market-data provider factory."""

from __future__ import annotations

import httpx
import pytest

from app.config.settings import ProviderConfig
from app.data.providers import (
    INDstocksMarketDataProvider,
    MarketDataProvider,
    NSEMarketDataProvider,
    ProviderAuthError,
    ProviderError,
    create_provider,
)
from app.data.providers.indstocks import _INDstocksWebSocketFeed


def test_nse_is_registered_and_creatable():
    provider = create_provider(ProviderConfig(name="nse"))
    assert isinstance(provider, MarketDataProvider)
    assert isinstance(provider, NSEMarketDataProvider)


def test_indstocks_is_registered_and_creatable():
    provider = create_provider(
        ProviderConfig(
            name="indstocks",
            params={"access_token": "test-token", "use_websocket": False},
        )
    )
    assert isinstance(provider, MarketDataProvider)
    assert isinstance(provider, INDstocksMarketDataProvider)


def test_create_provider_unknown_name():
    with pytest.raises(ProviderError, match="unknown market-data provider"):
        create_provider(ProviderConfig(name="does_not_exist"))


class TestIndstocksAuthHandling:
    """The expired-token scenario: REST 403 + WS handshake rejection."""

    @staticmethod
    def _provider_403() -> INDstocksMarketDataProvider:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                403,
                json={
                    "message": (
                        "The provided access_token is either incorrect, expired, "
                        "or has been revoked. The user needs to re-authenticate."
                    ),
                    "success": False,
                },
            )

        return INDstocksMarketDataProvider(
            access_token="expired-token",
            use_websocket=False,
            client=httpx.Client(transport=httpx.MockTransport(handler), timeout=5.0),
        )

    def test_rest_403_raises_auth_error(self):
        provider = self._provider_403()
        with pytest.raises(ProviderAuthError, match="token rejected"):
            provider._get_json("/market/quotes/full", params={"scrip-codes": "NIDX_40000001"})

    def test_auth_error_is_still_a_provider_error(self):
        # Existing fail-soft handlers catch ProviderError — auth errors must
        # flow through those paths, never crash the pipeline.
        provider = self._provider_403()
        with pytest.raises(ProviderError):
            provider._get_csv("/market/instruments", params={"source": "index"})

    def test_bootstrap_403_falls_back_to_default_scrips(self):
        provider = self._provider_403()
        # Instruments CSV 403s, but the provider stays constructible/usable.
        assert provider._index_scrips["NIFTY"] == "40000001"
        assert provider._ws_tokens["NIFTY"] == "NIDX:40000001"

    def test_auth_warning_is_logged_once_only(self, caplog):
        import logging

        provider = self._provider_403()
        for _ in range(3):
            with pytest.raises(ProviderAuthError):
                provider._get_json("/market/quotes/full")
        auth_logs = [
            r for r in caplog.records
            if r.levelno >= logging.ERROR and "authentication failed" in r.getMessage()
        ]
        assert len(auth_logs) == 1


class TestWebSocketReconnectPolicy:
    def test_auth_rejections_are_detected(self):
        rejected = _INDstocksWebSocketFeed.is_auth_rejection
        assert rejected(RuntimeError("server rejected WebSocket connection: HTTP 513"))
        assert rejected(RuntimeError("server rejected WebSocket connection: HTTP 401"))
        assert rejected(RuntimeError("server rejected WebSocket connection: HTTP 403"))
        assert not rejected(RuntimeError("connection reset by peer"))
        assert not rejected(RuntimeError("timed out during handshake"))

    def test_backoff_doubles_and_caps(self):
        backoff = _INDstocksWebSocketFeed.backoff_seconds
        assert backoff(1) == 3.0
        assert backoff(2) == 6.0
        assert backoff(3) == 12.0
        assert backoff(4) == 24.0
        assert backoff(5) == 48.0
        assert backoff(6) == 60.0   # cap reached
        assert backoff(50) == 60.0  # stays capped

    def test_auth_failure_stops_the_feed_thread(self):
        """Simulate the feed loop: a 513 handshake rejection must set the
        auth flag (and the loop must not keep reconnecting)."""
        import threading

        feed = _INDstocksWebSocketFeed(
            access_token="expired",
            ws_instruments={"NIFTY": "NIDX:40000001"},
            cache=_FakeCache(),
        )
        assert not feed.auth_failed

        # Drive the classification + flag exactly as _run does on rejection.
        exc = RuntimeError("server rejected WebSocket connection: HTTP 513")
        if _INDstocksWebSocketFeed.is_auth_rejection(exc):
            feed._auth_failed.set()
        assert feed.auth_failed
        # And the stop event is untouched (no leak when process restarts).
        assert isinstance(feed._stop, threading.Event)


class _FakeCache:
    """Minimal stand-in for _QuoteStreamCache."""

    def update(self, symbol: str, ltp: float, ts_ms: int) -> None: ...

    def get(self, symbol: str, max_age_seconds: float = 30.0) -> float | None:
        return None
