"""Configuration loading and validation.

Secrets are NEVER stored in YAML. The configuration pipeline is:

    YAML (defaults, non-secret)
      +  environment variables / .env  (secrets + overrides)
      ->  ``Settings`` (validated Pydantic model)

Secret values (Firebase credentials, Gemini API key, Telegram token) come
exclusively from the environment via :data:`ENV_OVERRIDES`.
"""

from __future__ import annotations

from .settings import (
    DEFAULT_CONFIG_PATH,
    ENV_OVERRIDES,
    ConfigError,
    Settings,
    load_settings,
)

__all__ = [
    "ConfigError",
    "DEFAULT_CONFIG_PATH",
    "ENV_OVERRIDES",
    "Settings",
    "load_settings",
]