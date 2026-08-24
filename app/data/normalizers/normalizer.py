"""Market-data normalizers.

Normalizers translate provider-neutral raw payloads into validated internal
models. A payload that fails normalization raises :class:`NormalizerError`;
the collector treats that as a data-quality failure.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.data.providers.base import ProviderError
from app.models.candle import MarketCandle, MarketQuote
from app.models.enums import OptionType
from app.models.instruments import FutureContract
from app.models.options import OptionChainEntry, OptionChainSnapshot
from app.models.snapshots import BreadthSnapshot
from app.models.derivatives import FIIDIIFlow, FuturesSnapshot


class NormalizerError(ProviderError):
    """Raised when a provider payload cannot be normalised."""


class MarketDataNormalizer:
    """Convert provider-neutral dict payloads into internal models."""

    # -- quotes --------------------------------------------------------
    def normalize_quote(self, payload: dict[str, Any], symbol: str) -> MarketQuote:
        try:
            return MarketQuote(
                symbol=symbol,
                timestamp=self._as_datetime(payload["timestamp"]),
                bid=payload.get("bid"),
                ask=payload.get("ask"),
                last_price=payload.get("last_price"),
                bid_size=payload.get("bid_size"),
                ask_size=payload.get("ask_size"),
                volume=int(payload.get("volume", 0)),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise NormalizerError(
                f"cannot normalize quote for {symbol}: {exc}"
            ) from exc

    def normalize_quotes(
        self, payloads: list[dict[str, Any]]
    ) -> dict[str, MarketQuote]:
        return {
            p["symbol"].upper(): self.normalize_quote(p, p["symbol"].upper())
            for p in payloads
        }

    # -- candles -------------------------------------------------------
    def normalize_candle_list(
        self, payloads: list[dict[str, Any]]
    ) -> list[MarketCandle]:
        return [self.normalize_candle(p) for p in payloads]

    def normalize_candle(self, payload: dict[str, Any]) -> MarketCandle:
        try:
            return MarketCandle(
                symbol=payload["symbol"].upper(),
                timestamp=self._as_datetime(payload["timestamp"]),
                open_price=float(payload["open"]),
                high_price=float(payload["high"]),
                low_price=float(payload["low"]),
                close_price=float(payload["close"]),
                volume=int(payload.get("volume", 0)),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise NormalizerError(f"cannot normalize candle: {exc}") from exc

    # -- option chain -------------------------------------------------------
    def normalize_entry(self, payload: dict[str, Any]) -> OptionChainEntry:
        try:
            return OptionChainEntry(
                strike=float(payload["strike"]),
                option_type=OptionType(payload["option_type"]),
                expiry_date=self._as_datetime(payload["expiry_date"]),
                open_interest=int(payload.get("open_interest", 0)),
                change_in_oi=payload.get("change_in_oi"),
                price_change_pct=payload.get("price_change_pct"),
                last_price=payload.get("last_price"),
                bid=payload.get("bid"),
                ask=payload.get("ask"),
                iv=payload.get("iv"),
                delta=payload.get("delta"),
                gamma=payload.get("gamma"),
                theta=payload.get("theta"),
                vega=payload.get("vega"),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise NormalizerError(f"cannot normalize option entry: {exc}") from exc

    def normalize_chain(self, payload: dict[str, Any]) -> OptionChainSnapshot:
        try:
            expiry = self._as_datetime(payload["expiry_date"])
            entries = []
            for e in payload.get("entries", []):
                e = dict(e)
                e.setdefault("expiry_date", payload["expiry_date"])
                entries.append(self.normalize_entry(e))
            return OptionChainSnapshot(
                underlying_symbol=payload["underlying_symbol"].upper(),
                timestamp=self._as_datetime(payload["timestamp"]),
                spot_price=float(payload["spot_price"]),
                expiry_date=expiry,
                entries=entries,
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise NormalizerError(f"cannot normalize option chain: {exc}") from exc

    # -- futures -----------------------------------------------------------
    def normalize_futures(self, payload: dict[str, Any]) -> FuturesSnapshot:
        try:
            contract_p = payload["contract"]
            contract = FutureContract(
                symbol=contract_p["symbol"].upper(),
                name=contract_p.get("name", ""),
                underlying_symbol=contract_p["underlying_symbol"].upper(),
                expiry_date=self._as_datetime(contract_p["expiry_date"]),
                contract_size=int(contract_p["contract_size"]),
                lot_size=int(contract_p["lot_size"]),
                tick_size=float(contract_p.get("tick_size", 0.05)),
            )
            quote = self.normalize_quote(
                payload["quote"], contract.underlying_symbol
            )
            return FuturesSnapshot(contract=contract, quote=quote)
        except (KeyError, ValueError, TypeError) as exc:
            raise NormalizerError(f"cannot normalize futures data: {exc}") from exc

    # -- breadth / vix / flows -------------------------------------------------
    def normalize_breadth(self, payload: dict[str, Any]) -> BreadthSnapshot:
        try:
            return BreadthSnapshot(
                timestamp=self._as_datetime(payload["timestamp"]),
                advancers=int(payload["advancers"]),
                decliners=int(payload["decliners"]),
                unchanged=int(payload["unchanged"]),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise NormalizerError(f"cannot normalize breadth: {exc}") from exc

    def normalize_fii_dii(self, payload: dict[str, Any]) -> FIIDIIFlow:
        try:
            return FIIDIIFlow(
                timestamp=self._as_datetime(payload["timestamp"]),
                fii_cash_net=payload.get("fii_cash_net"),
                dii_cash_net=payload.get("dii_cash_net"),
                fii_index_futures_net=payload.get("fii_index_futures_net"),
                fii_index_options_net=payload.get("fii_index_options_net"),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise NormalizerError(f"cannot normalize FII/DII flow: {exc}") from exc

    @staticmethod
    def _as_datetime(value: Any) -> datetime:
        return datetime.fromisoformat(value) if isinstance(value, str) else value
