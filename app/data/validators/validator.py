"""Deterministic market-data validation.

Every snapshot must pass rule-based validation covering:

* missing values
* duplicate timestamps
* invalid timestamps (naive/future)
* stale prices
* impossible OHLC relationships (enforced by models)
* invalid option strikes
* invalid expiry dates
* missing bid/ask where required
* abnormal spreads
* market-hour inconsistencies

The result is a :class:`DataQualityReport` whose status is one of
``VALID`` / ``WARNING`` / ``INVALID``. The signal engine must refuse to act
on anything that is not ``VALID``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.config.settings import DataQualityConfig, TradingSession
from app.models.candle import MarketCandle, MarketQuote
from app.models.enums import DataQuality
from app.models.options import OptionChainSnapshot
from app.models.snapshots import BreadthSnapshot
from app.models.time import now_ist
from app.models.validation import DataQualityReport, QualityIssue


class MarketDataValidator:
    """Runs deterministic validation rules over normalized data models."""

    def __init__(self, config: DataQualityConfig) -> None:
        self.config = config

    def validate_quote(
        self,
        quote: MarketQuote,
        *,
        now: datetime | None = None,
    ) -> DataQualityReport:
        report = DataQualityReport(
            symbol=quote.symbol, collected_at=now or now_ist()
        )
        now = now or now_ist()

        if quote.timestamp.tzinfo is None:
            report.add_issue(QualityIssue(code="naive_timestamp",
                                          message="timestamp is naive",
                                          severity=DataQuality.INVALID,
                                          field="timestamp"))
        if quote.timestamp > now + timedelta(minutes=5):
            report.add_issue(QualityIssue(code="future_timestamp",
                                          message="timestamp is in the future",
                                          severity=DataQuality.INVALID,
                                          field="timestamp"))
        age = (now - quote.timestamp).total_seconds()
        if age > self.config.max_staleness_seconds:
            report.add_issue(QualityIssue(
                code="stale_quote",
                message=f"quote is {int(age)}s old "
                        f"(max {self.config.max_staleness_seconds}s)",
                severity=DataQuality.WARNING, field="timestamp"))
        if self.config.require_bid_ask:
            if quote.bid is None or quote.ask is None:
                report.add_issue(QualityIssue(
                    code="missing_bid_ask",
                    message="bid/ask required but missing",
                    severity=DataQuality.INVALID, field="bid/ask"))
            else:
                spread = self._spread_pct(quote.bid, quote.ask)
                if spread > self.config.max_spread_pct:
                    report.add_issue(QualityIssue(
                        code="abnormal_spread",
                        message=f"spread {spread:.3f}% exceeds "
                                f"max {self.config.max_spread_pct}%",
                        severity=DataQuality.WARNING, field="bid/ask"))
        report.mark_run()
        return report

    def validate_candle(
        self,
        candle: MarketCandle,
        *,
        now: datetime | None = None,
        sessions: dict[str, TradingSession] | None = None,
    ) -> DataQualityReport:
        report = DataQualityReport(
            symbol=candle.symbol, collected_at=now or now_ist()
        )
        now = now or now_ist()
        if candle.timestamp.tzinfo is None:
            report.add_issue(QualityIssue(code="naive_timestamp",
                                          message="timestamp is naive",
                                          severity=DataQuality.INVALID))
        age = (now - candle.timestamp).total_seconds()
        if age > self.config.max_staleness_seconds:
            report.add_issue(QualityIssue(
                code="stale_candle",
                message=f"candle is {int(age)}s old",
                severity=DataQuality.WARNING))
        if self.config.check_market_hours and not self._in_session(
            candle.timestamp, sessions
        ):
            report.add_issue(QualityIssue(
                code="outside_market_hours",
                message=f"candle timestamp {candle.timestamp.isoformat()} "
                        "is outside configured sessions",
                severity=DataQuality.WARNING))
        report.mark_run()
        return report

    def validate_candles(
        self,
        candles: list[MarketCandle],
        *,
        now: datetime | None = None,
        sessions: dict[str, TradingSession] | None = None,
    ) -> DataQualityReport:
        first = candles[0] if candles else None
        report = DataQualityReport(
            symbol=first.symbol if first else "?",
            collected_at=now or now_ist(),
        )
        timestamps = [c.timestamp for c in candles]
        if len(timestamps) != len(set(timestamps)):
            report.add_issue(QualityIssue(code="duplicate_timestamps",
                message="duplicate timestamps present", severity=DataQuality.INVALID))
        if candles and any(c.timestamp.tzinfo is None for c in candles):
            report.add_issue(QualityIssue(code="naive_timestamp",
                message="one or more naive timestamps",
                severity=DataQuality.INVALID))
        report.mark_run()
        return report

    def validate_chain(
        self,
        chain: OptionChainSnapshot,
        *,
        now: datetime | None = None,
    ) -> DataQualityReport:
        report = DataQualityReport(
            symbol=chain.underlying_symbol, collected_at=now or now_ist()
        )
        if chain.expiry_date <= chain.timestamp:
            report.add_issue(QualityIssue(code="expired_chain",
                message="expiry_date is not after snapshot timestamp",
                severity=DataQuality.INVALID))
        if not chain.entries:
            report.add_issue(QualityIssue(code="empty_chain",
                message="chain has no entries", severity=DataQuality.WARNING))
        strikes = [e.strike for e in chain.entries]
        if any(s <= 0 for s in strikes):
            report.add_issue(QualityIssue(code="invalid_strike",
                message="strike <= 0 present", severity=DataQuality.INVALID))
        has_calls = any(e.is_call for e in chain.entries)
        has_puts = any(e.is_put for e in chain.entries)
        if not (has_calls and has_puts):
            report.add_issue(QualityIssue(code="one_sided_chain",
                message="chain missing calls or puts",
                severity=DataQuality.WARNING))
        report.mark_run()
        return report

    def validate_breadth(
        self, breadth: BreadthSnapshot, *, now: datetime | None = None
    ) -> DataQualityReport:
        report = DataQualityReport(symbol="MKT", collected_at=now or now_ist())
        if breadth.total <= 0:
            report.add_issue(QualityIssue(code="empty_breadth",
                message="breadth totals zero", severity=DataQuality.WARNING))
        report.mark_run()
        return report

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _spread_pct(bid: float, ask: float) -> float:
        mid = (bid + ask) / 2
        return 0.0 if mid <= 0 else (ask - bid) / mid * 100.0

    @staticmethod
    def _in_session(
        dt: datetime, sessions: dict[str, TradingSession] | None
    ) -> bool:
        if not sessions:
            return True
        weekday = dt.weekday()
        t = dt.time()
        for session in sessions.values():
            if weekday not in session.days:
                continue
            sh, sm = map(int, session.start.split(":"))
            eh, em = map(int, session.end.split(":"))
            start = datetime(1900, 1, 1, sh, sm).time()
            end = datetime(1900, 1, 1, eh, em).time()
            if start <= t <= end:
                return True
        return False