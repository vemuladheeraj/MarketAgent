"""Unit tests for the configuration system."""

from __future__ import annotations

import pytest

from app.config import ConfigError, load_settings
from app.config.settings import (
    ENV_OVERRIDES,
    DEFAULT_CONFIG_PATH,
    ScoreBands,
    SignalConfig,
)


def _raw() -> dict:
    return {
        "environment": "development",
        "market": {
            "timezone": "Asia/Kolkata",
            "sessions": {
                "equity_cash": {"start": "09:15", "end": "15:30", "days": [0, 1, 2, 3, 4]},
            },
            "instruments": [{"symbol": "NIFTY", "kind": "index"}],
        },
        "signal": {
            "weights": {
                "trend": 15,
                "momentum": 10,
                "price_structure": 15,
                "volume": 10,
                "oi": 15,
                "options_structure": 15,
                "volatility": 10,
                "breadth": 5,
                "risk_reward": 5,
            }
        },
    }


class TestDefaultConfig:
    def test_loads_from_default_yaml(self, fresh_settings):
        s = fresh_settings
        assert s.environment == "development"
        assert s.market.timezone == "Asia/Kolkata"
        assert "equity_cash" in s.market.sessions

    def test_default_weights_sum_to_100(self, default_settings):
        assert abs(sum(default_settings.signal.weights.values()) - 100.0) < 1e-6

    def test_expected_risk_defaults(self, default_settings):
        risk = default_settings.risk
        assert risk.account_size == 1_000_000
        assert risk.risk_per_trade_pct == 1.0

    def test_environments_isolated_from_shell(self, fresh_settings):
        # The developer's shell environment must not leak secrets into tests.
        assert fresh_settings.gemini.api_key == ""


class TestEnvOverrides:
    def test_override_through_environ(self):
        data = _raw()
        data["gemini"] = {"api_key": "sk-yaml-should-be-replaced", "model": ""}
        s = load_settings(
            raw_data=data,
            environ={
                "GEMINI_API_KEY": "sk-env-secret",
                "GEMINI_MODEL": "gemini-test",
            },
        )
        assert s.gemini.api_key == "sk-env-secret"
        assert s.gemini.model == "gemini-test"

    def test_override_applied_only_when_present(self):
        data = _raw()
        s = load_settings(raw_data=data, environ={})
        assert s.gemini.api_key == ""

    def test_override_mapping_covers_secret_paths(self):
        assert ENV_OVERRIDES["GEMINI_API_KEY"] == ("gemini", "api_key")
        assert ENV_OVERRIDES["TELEGRAM_BOT_TOKEN"] == ("telegram", "bot_token")
        assert ENV_OVERRIDES["FIREBASE_CREDENTIALS_PATH"] == (
            "firestore",
            "credentials_path",
        )

    def test_overrides_argument_wins(self):
        data = _raw()
        s = load_settings(raw_data=data, overrides={"signal.min_signal_score": 80})
        assert s.signal.min_signal_score == 80


class TestValidationFailures:
    def test_weights_must_sum_to_100(self):
        data = _raw()
        data["signal"]["weights"]["trend"] = 50
        with pytest.raises(ConfigError):
            load_settings(raw_data=data, environ={})

    def test_invalid_session_time_rejected(self):
        data = _raw()
        data["market"]["sessions"]["equity_cash"]["start"] = "25:99"
        with pytest.raises(ConfigError):
            load_settings(raw_data=data, environ={})

    def test_production_requires_secrets(self):
        data = _raw()
        data["environment"] = "production"
        with pytest.raises(ConfigError, match="environment variables"):
            load_settings(raw_data=data, environ={})

    def test_production_accepts_when_secrets_present(self):
        data = _raw()
        data["environment"] = "production"
        data["firestore"] = {"project_id": "proj"}
        data["gemini"] = {"api_key": "key"}
        data["telegram"] = {"bot_token": "token", "chat_id": "123"}
        s = load_settings(raw_data=data, environ={})
        assert s.is_production()

    def test_missing_config_file_raises(self, tmp_path):
        with pytest.raises(ConfigError, match="not found"):
            load_settings(config_path=tmp_path / "nope.yaml", environ={})

    def test_unknown_timezone_rejected(self):
        data = _raw()
        data["market"]["timezone"] = "Mars/Olympus"
        with pytest.raises(ConfigError):
            load_settings(raw_data=data, environ={})

    def test_risk_per_trade_cannot_exceed_daily_loss(self):
        data = _raw()
        data["risk"] = {
            "account_size": 100000,
            "risk_per_trade_pct": 5,
            "max_daily_loss_pct": 2,
        }
        with pytest.raises(ConfigError):
            load_settings(raw_data=data, environ={})


class TestScoreBands:
    def test_bands_strictly_increasing(self):
        ScoreBands(no_trade=0, weak=50, watch=60, valid=70,
                   high_quality=80, exceptional=90)

    def test_bands_reject_flat(self):
        with pytest.raises(ValueError):
            ScoreBands(no_trade=50, weak=50)

    def test_signal_config_weights_validation(self):
        with pytest.raises(ValueError):
            SignalConfig(weights={"trend": 50})


class TestConfigPath:
    def test_default_path_points_to_repo(self):
        assert DEFAULT_CONFIG_PATH.name == "default.yaml"
        assert DEFAULT_CONFIG_PATH.read_text(encoding="utf-8").startswith("#")