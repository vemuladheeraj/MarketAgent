"""Provider factory — resolves a configured provider name to an instance."""

from __future__ import annotations

from app.config.settings import ProviderConfig
from app.data.providers.base import MarketDataProvider, ProviderError
from app.data.providers.indstocks import INDstocksMarketDataProvider
from app.data.providers.nse import NSEMarketDataProvider

#: Registry of available providers keyed by ``.name``.
PROVIDER_REGISTRY: dict[str, type[MarketDataProvider]] = {
    NSEMarketDataProvider.name: NSEMarketDataProvider,
    INDstocksMarketDataProvider.name: INDstocksMarketDataProvider,
}


def register_provider(cls: type[MarketDataProvider]) -> type[MarketDataProvider]:
    """Class decorator to register a new provider implementation."""
    PROVIDER_REGISTRY[cls.name] = cls
    return cls


def create_provider(config: ProviderConfig) -> MarketDataProvider:
    """Instantiate the provider named in ``config.name``.

    Raises
    ------
    ProviderError
        When the provider name is not registered.
    """
    name = (config.name or "").strip().lower()
    provider_cls = PROVIDER_REGISTRY.get(name)
    if provider_cls is None:
        raise ProviderError(
            f"unknown market-data provider {name!r}; "
            f"registered: {sorted(PROVIDER_REGISTRY)}"
        )
    params = dict(config.params or {})
    try:
        return provider_cls(**params)
    except TypeError as exc:
        raise ProviderError(
            f"cannot instantiate provider {name!r} with params {params}: {exc}"
        ) from exc