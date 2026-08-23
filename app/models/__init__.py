"""Domain models for the Indian Market Intelligence agent.

Phase 1 provides the fundamental data containers and enums. Analysis-result
models (TechnicalIndicators, OptionMetrics, Signal, RiskAssessment,
BacktestResult, GeminiAnalysis, …) are introduced alongside the engines that
produce them in later phases so that no model ships as an empty placeholder.
"""

from app.models.candle import MarketCandle, MarketQuote
from app.models.derivatives import FIIDIIFlow, FuturesSnapshot
from app.models.enums import (
    DataQuality,
    Direction,
    InstrumentKind,
    MarketRegime,
    Moneyness,
    OptionType,
    PositionBuild,
    SignalClassification,
    SystemEventType,
    TradeStage,
)
from app.models.events import Alert, Severity, SystemEvent
from app.models.instruments import FutureContract, Instrument, OptionContract
from app.models.options import OptionChainEntry, OptionChainSnapshot
from app.models.options_analysis import (
    OISummary,
    OptionGreeks,
    OptionMetrics,
    StrikePositionAnalysis,
)
from app.models.snapshots import BreadthSnapshot, MarketSnapshot
from app.models.technical import MarketStructure, TechnicalIndicators
from app.models.time import IST, UTC, MARKET_TIMEZONE, ensure_ist, now_ist
from app.models.validation import DataQualityReport, QualityIssue

__all__ = [
    "Alert",
    "BreadthSnapshot",
    "DataQuality",
    "DataQualityReport",
    "Direction",
    "FIIDIIFlow",
    "FutureContract",
    "FuturesSnapshot",
    "Instrument",
    "InstrumentKind",
    "IST",
    "MARKET_TIMEZONE",
    "MarketCandle",
    "MarketQuote",
    "MarketRegime",
    "MarketSnapshot",
    "MarketStructure",
    "Moneyness",
    "OISummary",
    "OptionChainEntry",
    "OptionChainSnapshot",
    "OptionContract",
    "OptionGreeks",
    "OptionMetrics",
    "OptionType",
    "PositionBuild",
    "QualityIssue",
    "Severity",
    "SignalClassification",
    "StrikePositionAnalysis",
    "SystemEvent",
    "SystemEventType",
    "TechnicalIndicators",
    "TradeStage",
    "UTC",
    "ensure_ist",
    "now_ist",
]