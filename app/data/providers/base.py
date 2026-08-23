"""Market-data provider abstraction.

Providers are adapters to *external* data sources (live NSE feeds, broker
APIs, replay files, or synthetic mocks). They return provider-neutral Python
dicts (documented per method); the :class:`MarketDataNormalizer` converts
those payloads into validated internal models.

The abstraction keeps analysis code completely decoupled from the data
vendor. In development, the clearly-labelled ``MockMarketDataProvider`` is
used; it never pretends to be live market data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any

#: Provider methods return plain dict payloads (documented schemas) so that
#: the interface stays vendor-neutral and normalizers own validation.
RawPayload = dict[str, Any]


class ProviderError(Exception):
    """Raised when a provider cannot fulfil a request."""


class MarketDataProvider(ABC):
    """Interface all market-data providers must implement."""

    #: unique registry key (e.g. "mock_replay", "nse", "broker_api")
    name: str = "base"

    @abstractmethod
    def get_quote(self, symbol: str) -> RawPayload:
        """Return a raw level-1 quote payload.

        Expected payload keys: ``symbol``, ``timestamp`` (ISO), ``bid``,
        ``ask``, ``last_price``, ``bid_size``, ``ask_size``, ``volume``.
        """

    @abstractmethod
    def get_candles(
        self, symbol: str, lookback_days: int = 30, timeframe: str = "1d"
    ) -> list[RawPayload]:
        """Return raw OHLCV candles (oldest first).

        Expected payload keys per bar: ``symbol``, ``timestamp``, ``open``,
        ``high``, ``low``, ``close``, ``volume``.
        """

    @abstractmethod
    def get_option_chain(
        self, symbol: str, expiry_date: datetime | date | None = None
    ) -> RawPayload:
        """Return a raw option chain for the given underlying/expiry.

        Expected payload keys: ``underlying_symbol``, ``timestamp``,
        ``spot_price``, ``expiry_date``, ``entries`` (list of dicts with
        ``strike``, ``option_type``, ``open_interest``, ``change_in_oi``,
        ``last_price``, ``bid``, ``ask``, ``iv``).
        """

    @abstractmethod
    def get_futures_data(self, symbol: str) -> RawPayload:
        """Return raw futures quote payload.

        Expected keys: ``contract`` (dict per FutureContract) and ``quote``
        (dict per MarketQuote).
        """

    @abstractmethod
    def get_market_breadth(self) -> RawPayload:
        """Return raw breadth payload: ``timestamp``, ``advancers``,
        ``decliners``, ``unchanged``."""

    @abstractmethod
    def get_vix(self) -> RawPayload:
        """Return raw VIX payload: ``symbol``, ``timestamp``, ``value``,
        ``change``."""

    @abstractmethod
    def get_fii_dii_data(self) -> RawPayload:
        """Return raw FII/DII flow payload (INR crores)."""

    # -- convenient helper for consumers -------------------------------
    @staticmethod
    def build_symbols(symbols: list[str]) -> list[str]:
        return [s.upper().strip() for s in symbols if s.strip()]