"""Market-data provider package."""

from app.data.providers.base import (
    MarketDataProvider,
    ProviderAuthError,
    ProviderError,
)
from app.data.providers.factory import (
    PROVIDER_REGISTRY,
    create_provider,
    register_provider,
)
from app.data.providers.indstocks import INDstocksMarketDataProvider
from app.data.providers.nse import NSEMarketDataProvider

__all__ = [
    "MarketDataProvider",
    "ProviderAuthError",
    "ProviderError",
    "PROVIDER_REGISTRY",
    "NSEMarketDataProvider",
    "INDstocksMarketDataProvider",
    "create_provider",
    "register_provider",
]
