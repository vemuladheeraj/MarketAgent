"""Shared test fixtures.

All fixtures are deterministic: configuration is read from the checked-in
default YAML (or supplied inline), and environment variables are isolated so
tests never depend on the developer's shell.
"""

from __future__ import annotations

import pytest

from app.config import DEFAULT_CONFIG_PATH, Settings, load_settings

MINIMAL_MARKET = {
    "timezone": "Asia/Kolkata",
    "sessions": {
        "equity_cash": {"start": "09:15", "end": "15:30", "days": [0, 1, 2, 3, 4]},
    },
    "instruments": [{"symbol": "NIFTY", "name": "NIFTY 50", "kind": "index"}],
}


@pytest.fixture()
def minimal_market_dict() -> dict:
    return MINIMAL_MARKET


@pytest.fixture(scope="session")
def default_settings() -> Settings:
    """Settings loaded from the checked-in ``config/default.yaml``."""
    return load_settings(
        config_path=DEFAULT_CONFIG_PATH,
        overrides={"provider.name": "nse", "provider.params": {}},
        environ={},
    )


@pytest.fixture()
def fresh_settings() -> Settings:
    """Per-test fresh copy of the default settings (env-isolated)."""
    return load_settings(
        config_path=DEFAULT_CONFIG_PATH,
        overrides={"provider.name": "nse", "provider.params": {}},
        environ={},
    )