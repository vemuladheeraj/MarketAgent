"""Shared enums used across the application layers."""

from __future__ import annotations

import enum


class InstrumentKind(str, enum.Enum):
    """Type of tradable/non-tradable instrument tracked by the system."""

    INDEX = "index"
    EQUITY = "equity"
    FUTURE = "future"
    OPTION = "option"


class OptionType(str, enum.Enum):
    CALL = "call"
    PUT = "put"


class Direction(str, enum.Enum):
    LONG = "long"
    SHORT = "short"


class DataQuality(str, enum.Enum):
    """Data-quality status produced by the validators.

    Only VALID data may feed the signal engine.
    """

    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


class MarketRegime(str, enum.Enum):
    """Deterministic market-regime labels produced by the regime engine."""

    STRONG_UPTREND = "strong_uptrend"
    UPTREND = "uptrend"
    RANGE = "range"
    DOWNTREND = "downtrend"
    STRONG_DOWNTREND = "strong_downtrend"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    EVENT_DRIVEN = "event_driven"
    UNCERTAIN = "uncertain"


class SignalClassification(str, enum.Enum):
    """Score-band labels for generated/considered signals."""

    NO_TRADE = "no_trade"
    WEAK = "weak"
    WATCH = "watch"
    VALID = "valid"
    HIGH_QUALITY = "high_quality"
    EXCEPTIONAL = "exceptional"


class TradeStage(str, enum.Enum):
    """Lifecycle stages of a paper trade.

    SIGNAL -> PAPER_ENTRY -> MONITOR -> EXIT -> RESULT
    """

    SIGNAL = "signal"
    PAPER_ENTRY = "paper_entry"
    MONITOR = "monitor"
    EXIT = "exit"
    RESULT = "result"


class PositionBuild(str, enum.Enum):
    """OI + price-change classification for options."""

    LONG_BUILDUP = "long_buildup"
    SHORT_BUILDUP = "short_buildup"
    SHORT_COVERING = "short_covering"
    LONG_UNWINDING = "long_unwinding"
    OI_UNCHANGED = "oi_unchanged"


class Moneyness(str, enum.Enum):
    ITM = "itm"
    ATM = "atm"
    OTM = "otm"


class SystemEventType(str, enum.Enum):
    """Event types emitted to observability/logging and systemEvents."""

    APP_START = "app_start"
    APP_STOP = "app_stop"
    DATA_RECEIVED = "data_received"
    DATA_VALIDATED = "data_validated"
    REGIME_DETECTED = "regime_detected"
    STRATEGY_EVALUATED = "strategy_evaluated"
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_REJECTED = "signal_rejected"
    RISK_REJECTED = "risk_rejected"
    PAPER_TRADE_OPENED = "paper_trade_opened"
    PAPER_TRADE_CLOSED = "paper_trade_closed"
    GEMINI_ANALYSIS_COMPLETED = "gemini_analysis_completed"
    TELEGRAM_ALERT_SENT = "telegram_alert_sent"
    ERROR = "error"