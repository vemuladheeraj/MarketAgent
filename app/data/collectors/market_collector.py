"""MarketDataCollector — composes provider + normalizer + validator.

The collector is the single entry point the rest of the system uses to obtain
a validated :class:`MarketSnapshot`. Provider failures degrade gracefully
(recorded as data-quality issues, never crashing the pipeline), and the
snapshot's ``meta["quality"]`` carries per-symbol quality summaries.
"""

from __future__ import annotations

import logging

from app.config.settings import DataQualityConfig, MarketConfig
from app.data.normalizers import MarketDataNormalizer
from app.data.providers import MarketDataProvider, ProviderError
from app.data.validators import MarketDataValidator
from app.models.snapshots import MarketSnapshot
from app.models.time import now_ist
from app.models.validation import DataQualityReport


class MarketDataCollector:
    def __init__(
        self,
        provider: MarketDataProvider,
        normalizer: MarketDataNormalizer | None = None,
        validator: MarketDataValidator | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.provider = provider
        self.normalizer = normalizer or MarketDataNormalizer()
        self.validator = validator
        self.logger = logger or logging.getLogger("market.data.collector")

    def collect_snapshot(
        self,
        market: MarketConfig,
        data_quality: DataQualityConfig,
    ) -> MarketSnapshot:
        """Fetch, normalize and validate one full market snapshot."""
        validator = self.validator or MarketDataValidator(data_quality)
        snapshot = MarketSnapshot(timestamp=now_ist())
        for instrument in market.instruments:
            self._collect_instrument(snapshot, instrument.symbol, validator)
        self._collect_breadth(snapshot, validator)
        self._collect_vix(snapshot, validator)
        self._collect_flows(snapshot, validator)
        snapshot.meta["provider"] = self.provider.name
        return snapshot

    # -- instrument -----------------------------------------------------
    def _collect_instrument(
        self,
        snapshot: MarketSnapshot,
        symbol: str,
        validator: MarketDataValidator,
    ) -> None:
        symbol = symbol.upper()
        try:
            raw_quote = self.provider.get_quote(symbol)
        except ProviderError as exc:
            self._record_error(snapshot, symbol, f"quote: {exc}")
            return
        try:
            quote = self.normalizer.normalize_quote(raw_quote, symbol)
        except ProviderError as exc:
            self._record_error(snapshot, symbol, f"quote-normalize: {exc}")
            return
        snapshot.quotes[symbol] = quote
        report = validator.validate_quote(quote)
        self._record_report(snapshot, symbol, report)
        if report.invalid:
            self.logger.warning("QUOTE_INVALID symbol=%s", symbol)
            return
        try:
            raw_chain = self.provider.get_option_chain(symbol)
        except ProviderError as exc:
            self._record_error(snapshot, symbol, f"option_chain: {exc}")
            return
        try:
            chain = self.normalizer.normalize_chain(raw_chain)
        except ProviderError as exc:
            self._record_error(snapshot, symbol, f"chain-normalize: {exc}")
            return
        snapshot.option_chains[symbol] = chain
        chain_report = validator.validate_chain(chain)
        self._record_report(snapshot, symbol, chain_report)

    # -- breadth / vix / flows ------------------------------------------
    def _collect_breadth(
        self, snapshot: MarketSnapshot, validator: MarketDataValidator
    ) -> None:
        try:
            raw = self.provider.get_market_breadth()
        except ProviderError as exc:
            self._record_error(snapshot, "MKT", f"breadth: {exc}")
            return
        snapshot.breadth = self.normalizer.normalize_breadth(raw)

    def _collect_vix(
        self, snapshot: MarketSnapshot, validator: MarketDataValidator
    ) -> None:
        try:
            raw = self.provider.get_vix()
        except ProviderError as exc:
            self._record_error(snapshot, "VIX", f"vix: {exc}")
            return
        snapshot.vix = float(raw["value"])

    def _collect_flows(
        self, snapshot: MarketSnapshot, validator: MarketDataValidator
    ) -> None:
        try:
            raw = self.provider.get_fii_dii_data()
        except ProviderError as exc:
            self._record_error(snapshot, "FLOW", f"fii_dii: {exc}")
            return
        flow = self.normalizer.normalize_fii_dii(raw)
        snapshot.fii_net_buy = flow.fii_cash_net
        snapshot.dii_net_buy = flow.dii_cash_net

    # -- helpers ----------------------------------------------------------
    def _record_report(
        self, snapshot: MarketSnapshot, symbol: str, report: DataQualityReport
    ) -> None:
        quality = snapshot.meta.setdefault("quality", {})
        issues = [i.code for i in report.issues]
        quality[symbol] = {"status": report.status.value, "issues": issues}

    def _record_error(
        self, snapshot: MarketSnapshot, symbol: str, message: str
    ) -> None:
        self.logger.error("PROVIDER_ERROR symbol=%s err=%s", symbol, message)
        quality = snapshot.meta.setdefault("quality", {})
        quality[symbol] = {"status": "invalid", "issues": [message]}