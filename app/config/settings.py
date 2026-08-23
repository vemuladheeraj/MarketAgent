"""Central configuration models and loader.

The settings tree mirrors ``config/default.yaml``. Every section from the
requirements (market, trading hours, provider, Firebase, Gemini, Telegram,
risk, transaction costs, signal thresholds, strategies, logging) is
represented by a typed model with validation.

Secret values default to empty strings and MUST be supplied through the
environment (see :data:`ENV_OVERRIDES`).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError, model_validator

try:
    import yaml
except ImportError as exc:  # pragma: no cover - only when deps are missing
    raise RuntimeError("PyYAML is required (pip install -r requirements.txt)") from exc

# --------------------------------------------------------------------------
# Paths & environment override map
# --------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "default.yaml"

#: Map of ``ENVIRONMENT_VARIABLE -> (nested_settings_path...)``.
#: Values from the environment are injected into the YAML-derived dict
#: *before* Pydantic validation. Missing/empty variables are left untouched.
ENV_OVERRIDES: dict[str, tuple[str, ...]] = {
    "APP_ENVIRONMENT": ("environment",),
    "APP_LOG_LEVEL": ("logging", "level"),
    "DATA_PROVIDER": ("provider", "name"),
    "DATA_PROVIDER_BASE_URL": ("provider", "base_url"),
    "FIREBASE_PROJECT_ID": ("firestore", "project_id"),
    "FIREBASE_CREDENTIALS_PATH": ("firestore", "credentials_path"),
    "FIRESTORE_DATABASE": ("firestore", "database"),
    "GEMINI_API_KEY": ("gemini", "api_key"),
    "GEMINI_MODEL": ("gemini", "model"),
    "TELEGRAM_BOT_TOKEN": ("telegram", "bot_token"),
    "TELEGRAM_CHAT_ID": ("telegram", "chat_id"),
}

#: Runtime environment names. ``production`` additionally requires secrets.
Environment = Literal["development", "testing", "production"]


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


# --------------------------------------------------------------------------
# Small value-objects
# --------------------------------------------------------------------------

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class TradingSession(BaseModel):
    """A recurring intraday trading session in the configured timezone."""

    name: str = ""
    start: str = Field(description="Local time 'HH:MM'")
    end: str = Field(description="Local time 'HH:MM'")
    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])

    @model_validator(mode="after")
    def _validate(self) -> "TradingSession":
        for value in (self.start, self.end):
            if not _TIME_RE.match(value):
                raise ValueError(f"time must be HH:MM, got {value!r}")
        invalid_days = [d for d in self.days if d not in range(7)]
        if invalid_days:
            raise ValueError(f"days must be in 0..6, got {invalid_days}")
        if not self.days:
            raise ValueError("days cannot be empty")
        return self


class ConfigInstrumentEntry(BaseModel):
    symbol: str
    name: str = ""
    kind: Literal["index", "equity", "future", "option"] = "index"


class MarketConfig(BaseModel):
    timezone: str = "Asia/Kolkata"
    sessions: dict[str, TradingSession]
    instruments: list[ConfigInstrumentEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> "MarketConfig":
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:  # pragma: no cover - env-specific
            raise ValueError(f"unknown timezone {self.timezone!r}") from exc
        return self


class ProviderConfig(BaseModel):
    name: str = "mock_replay"
    base_url: str = ""
    timeout_seconds: float = Field(default=10.0, gt=0)
    params: dict[str, Any] = Field(default_factory=dict)


class FirestoreConfig(BaseModel):
    project_id: str = ""
    database: str = "market"
    credentials_path: str = ""


class GeminiConfig(BaseModel):
    api_key: str = ""
    model: str = ""
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=2048, gt=0)


class TelegramConfig(BaseModel):
    bot_token: str = ""
    chat_id: str = ""


class RiskConfig(BaseModel):
    account_size: float = Field(default=1_000_000.0, gt=0)
    risk_per_trade_pct: float = Field(default=1.0, gt=0, le=100)
    max_daily_loss_pct: float = Field(default=3.0, gt=0, le=100)
    max_concurrent_paper_trades: int = Field(default=3, ge=1)
    max_trades_per_day: int = Field(default=5, ge=1)
    min_risk_reward: float = Field(default=1.5, gt=0)
    min_expected_value: float = Field(default=0.0)
    max_consecutive_losses: int = Field(default=3, ge=1)
    cooldown_after_loss_minutes: int = Field(default=60, ge=0)
    emergency_disable: bool = False

    @model_validator(mode="after")
    def _validate(self) -> "RiskConfig":
        if self.max_daily_loss_pct < self.risk_per_trade_pct:
            raise ValueError(
                "max_daily_loss_pct must be >= risk_per_trade_pct "
                f"({self.max_daily_loss_pct} < {self.risk_per_trade_pct})"
            )
        return self


class TransactionCostConfig(BaseModel):
    """Configurable Indian transaction-cost model (used from Phase 8).

    Percentages are applied to notional trade value *per side* unless
    documented otherwise.
    """

    brokerage: float = Field(default=0.0, ge=0)
    stt_buy_pct: float = Field(default=0.0, ge=0)
    stt_sell_pct: float = Field(default=0.025, ge=0)
    gst_pct: float = Field(default=18.0, ge=0)
    exchange_charges_pct: float = Field(default=0.045, ge=0)
    sebi_charges_pct: float = Field(default=0.0001, ge=0)
    stamp_duty_pct: float = Field(default=0.003, ge=0)
    slippage_pct: float = Field(default=0.05, ge=0)
    bid_ask_spread_pct: float = Field(default=0.02, ge=0)


class DataQualityConfig(BaseModel):
    """Tolerances for the market-data validator (Phase 2)."""

    max_staleness_seconds: float = Field(default=300, ge=0)
    max_spread_pct: float = Field(default=2.0, ge=0)
    max_price_move_pct: float = Field(default=30.0, ge=0)
    require_bid_ask: bool = True
    check_market_hours: bool = True
    check_duplicate_timestamps: bool = True
    check_future_timestamps: bool = True


class ScoreBands(BaseModel):
    """Score->classification thresholds (lower bound inclusive)."""

    no_trade: float = 0.0
    weak: float = 50.0
    watch: float = 60.0
    valid: float = 70.0
    high_quality: float = 80.0
    exceptional: float = 90.0

    @model_validator(mode="after")
    def _validate(self) -> "ScoreBands":
        ordered = [
            self.no_trade,
            self.weak,
            self.watch,
            self.valid,
            self.high_quality,
            self.exceptional,
        ]
        if any(b < 0 or b > 100 for b in ordered):
            raise ValueError("all bands must be within 0..100")
        for lower, upper in zip(ordered, ordered[1:]):
            if not lower < upper:
                raise ValueError("ScoreBands must be strictly increasing")
        return self


#: Initial signal scoring weights (documented in the specification).
DEFAULT_SIGNAL_WEIGHTS: dict[str, float] = {
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


class SignalConfig(BaseModel):
    min_signal_score: float = Field(default=70.0, ge=0, le=100)
    min_risk_reward: float = Field(default=1.5, gt=0)
    weights: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_SIGNAL_WEIGHTS)
    )
    bands: ScoreBands = ScoreBands()

    @model_validator(mode="after")
    def _validate(self) -> "SignalConfig":
        if not self.weights:
            raise ValueError("signal.weights must not be empty")
        if any(w < 0 for w in self.weights.values()):
            raise ValueError("signal weights must be >= 0")
        total = sum(self.weights.values())
        if abs(total - 100.0) > 0.01:
            raise ValueError(f"signal weights must sum to 100, got {total:.4f}")
        return self


class StrategyConfig(BaseModel):
    enabled: dict[str, bool] = Field(default_factory=dict)
    params: dict[str, dict[str, Any]] = Field(default_factory=dict)


class LoggingConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: str = "%(asctime)s %(levelname)s %(name)s %(message)s"
    file_enabled: bool = False
    file_path: str = "logs/app.log"


class Settings(BaseModel):
    """Fully validated application configuration."""

    environment: Environment = "development"
    market: MarketConfig
    provider: ProviderConfig = ProviderConfig()
    firestore: FirestoreConfig = FirestoreConfig()
    gemini: GeminiConfig = GeminiConfig()
    telegram: TelegramConfig = TelegramConfig()
    risk: RiskConfig = RiskConfig()
    transaction_costs: TransactionCostConfig = TransactionCostConfig()
    data_quality: DataQualityConfig = DataQualityConfig()
    signal: SignalConfig = SignalConfig()
    strategies: StrategyConfig = StrategyConfig()
    logging: LoggingConfig = LoggingConfig()

    # -- convenience -------------------------------------------------
    @property
    def timezone(self) -> str:
        return self.market.timezone

    def is_production(self) -> bool:
        return self.environment == "production"

    def has_no_secrets(self) -> bool:
        """True when none of the secret-bearing sections are configured."""
        return not (
            self.firestore.project_id
            or self.gemini.api_key
            or self.telegram.bot_token
        )

    @model_validator(mode="after")
    def _validate(self) -> "Settings":
        if self.environment == "production":
            missing = []
            if not self.firestore.project_id:
                missing.append("FIREBASE_PROJECT_ID")
            if not self.gemini.api_key:
                missing.append("GEMINI_API_KEY")
            if not self.telegram.bot_token or not self.telegram.chat_id:
                missing.append("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
            if missing:
                raise ValueError(
                    "production environment requires the following "
                    f"environment variables: {', '.join(missing)}"
                )
        return self


# --------------------------------------------------------------------------
# Loader
# --------------------------------------------------------------------------


def _apply_env_overrides(data: dict, environ: dict[str, str]) -> dict:
    """Inject non-empty environment variables into the settings dict."""
    for var, path in ENV_OVERRIDES.items():
        value = environ.get(var, "").strip()
        if not value:
            continue
        _set_nested(data, path, value)
    return data


def _set_nested(data: dict, path: tuple[str, ...], value: Any) -> None:
    node = data
    for key in path[:-1]:
        child = node.setdefault(key, {})
        if not isinstance(child, dict):
            raise ConfigError(f"cannot override non-dict config at {key!r}")
        node = child
    node[path[-1]] = value


def _resolve_config_path(config_path: str | Path | None) -> Path:
    if config_path is not None:
        candidate = Path(config_path)
    else:
        env_path = os.environ.get("APP_CONFIG_PATH", "").strip()
        candidate = Path(env_path) if env_path else DEFAULT_CONFIG_PATH
    if not candidate.is_file():
        raise ConfigError(
            f"configuration file not found: {candidate} "
            "(set APP_CONFIG_PATH to override)"
        )
    return candidate


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        raise ConfigError(f"cannot read configuration file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"configuration file {path} must contain a mapping")
    return data


def load_settings(
    config_path: str | Path | None = None,
    env_file: str | Path | None = None,
    overrides: dict[str, Any] | None = None,
    environ: dict[str, str] | None = None,
    *,
    raw_data: dict[str, Any] | None = None,
) -> Settings:
    """Load and validate :class:`Settings`.

    Parameters
    ----------
    config_path:
        Path to the YAML config; defaults to ``APP_CONFIG_PATH`` or
        ``config/default.yaml``.
    env_file:
        Optional ``.env`` file to load before resolving the environment.
    overrides:
        Explicit flat- or nested-key overrides applied last (tests/CLI).
    environ:
        Environment mapping; defaults to ``os.environ`` (tests inject here).
    raw_data:
        Skip file reading and load from this mapping directly (test hook).
    """
    if env_file is not None:
        load_dotenv(str(env_file), override=True)

    if raw_data is not None:
        data = dict(raw_data)
    else:
        data = _read_yaml(_resolve_config_path(config_path))

    env = dict(os.environ if environ is None else environ)
    _apply_env_overrides(data, env)

    if overrides:
        for key, value in overrides.items():
            _set_nested(data, tuple(key.split(".")), value)

    try:
        return Settings.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"invalid configuration: {exc}") from exc