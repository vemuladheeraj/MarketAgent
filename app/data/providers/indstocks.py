"""INDstocks broker API market-data provider.

Uses the free INDstocks REST API for live quotes, option chains, and historical
candles. A background WebSocket feed keeps index LTPs fresh between pipeline
cycles. VIX, market breadth, and FII/DII are delegated to the public NSE
provider because INDstocks does not expose those endpoints.

Requires an INDstocks account, completed KYC, and a 24-hour access token from:
https://indstocks.com/app/api-trading/access-tokens
"""

from __future__ import annotations

import csv
import io
import json
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from app.data.providers.base import (
    MarketDataProvider,
    ProviderAuthError,
    ProviderError,
    RawPayload,
)
from app.data.providers.nse import NSEMarketDataProvider
from app.logging.setup import get_logger
from app.models.time import IST, now_ist

logger = get_logger("data.provider.indstocks")

DEFAULT_BASE_URL = "https://api.indstocks.com"
WS_URL = "wss://ws-prices.indstocks.com/api/v1/ws/prices"

#: Logical symbol -> INDstocks index instrument name aliases (column 2 in index CSV).
SYMBOL_INDEX_NAMES: dict[str, list[str]] = {
    "NIFTY": ["NIFTY 50", "NIFTY", "NIFTY50"],
    "BANKNIFTY": ["BANK NIFTY", "NIFTY BANK", "BANKNIFTY"],
    "FINNIFTY": ["NIFTY FINANCIAL", "NIFTY FINANCIAL SERVICES", "NIFTYFINSRV25 50", "FINNIFTY"],
    "SENSEX": ["SENSEX", "BSE SENSEX"],
}

#: FNO ``SYMBOL_NAME`` values used when discovering option expiries.
SYMBOL_FNO_NAMES: dict[str, str] = {
    "NIFTY": "NIFTY",
    "BANKNIFTY": "BANKNIFTY",
    "FINNIFTY": "FINNIFTY",
    "SENSEX": "SENSEX",
}

DEFAULT_LOT_SIZES: dict[str, int] = {
    "NIFTY": 75,
    "BANKNIFTY": 30,
    "FINNIFTY": 40,
    "SENSEX": 20,
}


class _QuoteStreamCache:
    """Thread-safe store for WebSocket LTP/quote ticks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ltp: dict[str, tuple[float, int]] = {}  # symbol -> (price, ts_ms)

    def update(self, symbol: str, ltp: float, ts_ms: int) -> None:
        with self._lock:
            self._ltp[symbol.upper()] = (ltp, ts_ms)

    def get(self, symbol: str, max_age_seconds: float = 30.0) -> float | None:
        sym = symbol.upper()
        with self._lock:
            entry = self._ltp.get(sym)
        if entry is None:
            return None
        ltp, ts_ms = entry
        age = time.time() - (ts_ms / 1000.0)
        if age > max_age_seconds:
            return None
        return ltp


class _INDstocksWebSocketFeed:
    """Background price WebSocket that caches live LTP per symbol.

    Reconnect behaviour
    -------------------
    * Transient disconnects retry with exponential backoff (3s doubling to a
      60s cap) and log at most once per 10 consecutive failures so the log
      stays readable during outages.
    * Handshake rejections that indicate bad/expired credentials
      (HTTP 401/403/513) stop the feed entirely after ONE actionable error —
      hammering the server with a dead token serves nobody.
    """

    #: WS handshake statuses that mean the token is dead, not the network.
    AUTH_REJECT_STATUSES = (401, 403, 513)
    RECONNECT_MIN_SECONDS = 3.0
    RECONNECT_MAX_SECONDS = 60.0

    def __init__(
        self,
        *,
        access_token: str,
        ws_instruments: dict[str, str],
        cache: _QuoteStreamCache,
    ) -> None:
        self._token = access_token
        self._ws_instruments = ws_instruments  # symbol -> "NIDX:token"
        self._cache = cache
        self._stop = threading.Event()
        self._auth_failed = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def auth_failed(self) -> bool:
        """True when the feed stopped because the token was rejected."""
        return self._auth_failed.is_set()

    @classmethod
    def is_auth_rejection(cls, exc: Exception) -> bool:
        """True when a WS handshake failure looks like bad/expired auth."""
        text = str(exc)
        return any(f"HTTP {code}" in text for code in cls.AUTH_REJECT_STATUSES)

    @staticmethod
    def backoff_seconds(consecutive_failures: int) -> float:
        """Exponential reconnect backoff: 3s doubling to a 60s cap."""
        delay = _INDstocksWebSocketFeed.RECONNECT_MIN_SECONDS * (
            2 ** max(0, consecutive_failures - 1)
        )
        return min(delay, _INDstocksWebSocketFeed.RECONNECT_MAX_SECONDS)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="indstocks-ws", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            from websockets.sync.client import connect
        except ImportError:
            logger.warning("websockets package not installed; live WS feed disabled")
            return

        token_to_symbol = {v.split(":", 1)[1]: k for k, v in self._ws_instruments.items()}
        instruments = list(self._ws_instruments.values())
        consecutive_failures = 0

        while not self._stop.is_set():
            try:
                with connect(
                    WS_URL,
                    additional_headers={"Authorization": self._token},
                    open_timeout=15,
                    close_timeout=5,
                ) as ws:
                    consecutive_failures = 0
                    ws.send(
                        json.dumps(
                            {
                                "action": "subscribe",
                                "mode": "ltp",
                                "instruments": instruments,
                            }
                        )
                    )
                    logger.info("INDstocks WebSocket subscribed to %d instruments", len(instruments))
                    while not self._stop.is_set():
                        try:
                            raw = ws.recv(timeout=30)
                        except TimeoutError:
                            continue
                        if not raw:
                            continue
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8", errors="replace")
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(msg, dict) or msg.get("mode") != "ltp":
                            continue
                        inst_token = str(msg.get("instrument", ""))
                        symbol = token_to_symbol.get(inst_token)
                        if not symbol:
                            continue
                        data = msg.get("data") or {}
                        ltp = data.get("ltp")
                        ts_ms = int(msg.get("timestamp") or time.time() * 1000)
                        if ltp is not None:
                            self._cache.update(symbol, float(ltp), ts_ms)
            except Exception as exc:
                if self._stop.is_set():
                    break
                if self.is_auth_rejection(exc):
                    self._auth_failed.set()
                    logger.error(
                        "INDstocks WebSocket rejected (%s). The access token is expired, "
                        "incorrect, or revoked — generate a fresh 24h token at "
                        "https://indstocks.com/app/api-trading/access-tokens, update "
                        "INDSTOCKS_ACCESS_TOKEN in .env, and restart run_live.ps1. "
                        "WS feed stopped; quotes fall back to REST until then.",
                        exc,
                    )
                    break
                consecutive_failures += 1
                delay = self.backoff_seconds(consecutive_failures)
                if consecutive_failures == 1 or consecutive_failures % 10 == 0:
                    logger.warning(
                        "INDstocks WebSocket disconnected: %s — reconnecting "
                        "(attempt %d, next in %.0fs)",
                        exc,
                        consecutive_failures,
                        delay,
                    )
                self._stop.wait(delay)


class INDstocksMarketDataProvider(MarketDataProvider):
    """Live market data via the INDstocks REST + WebSocket APIs.

    Parameters
    ----------
    access_token:
        INDstocks API access token (24-hour validity).
    base_url:
        API base URL (default ``https://api.indstocks.com``).
    timeout_seconds:
        HTTP timeout.
    use_websocket:
        When True, start a background WebSocket LTP feed for realtime quotes.
    strike_count:
        Strikes per side of ATM for option-chain requests.
    cache_ttl_seconds:
        Short REST response cache to avoid duplicate calls within one cycle.
    """

    name = "indstocks"

    def __init__(
        self,
        *,
        access_token: str = "",
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 10.0,
        use_websocket: bool = True,
        strike_count: int = 20,
        cache_ttl_seconds: float = 1.0,
        client: httpx.Client | None = None,
    ) -> None:
        token = (access_token or "").strip()
        if not token:
            raise ProviderError(
                "INDstocks access token is required. Set INDSTOCKS_ACCESS_TOKEN in .env "
                "or provider.params.access_token — generate at "
                "https://indstocks.com/app/api-trading/access-tokens"
            )

        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.strike_count = strike_count
        self.cache_ttl_seconds = cache_ttl_seconds
        self._token = token
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._headers = {"Authorization": token}

        # Resolved at startup from INDstocks instruments master
        self._index_scrips: dict[str, str] = {}  # symbol -> underlying SECURITY_ID
        self._ws_tokens: dict[str, str] = {}  # symbol -> NIDX:token
        self._lot_sizes: dict[str, int] = dict(DEFAULT_LOT_SIZES)

        self._quote_cache = _QuoteStreamCache()
        self._ws_feed: _INDstocksWebSocketFeed | None = None
        if use_websocket:
            self._ws_feed = _INDstocksWebSocketFeed(
                access_token=token,
                ws_instruments={},  # populated after instrument bootstrap
                cache=self._quote_cache,
            )

        self._rest_cache: dict[str, tuple[float, Any]] = {}
        self._expiry_cache: dict[str, tuple[float, list[str]]] = {}
        self._nse_fallback: NSEMarketDataProvider | None = None
        self._auth_warned = False

        self._bootstrap_instruments()
        if self._ws_feed is not None and self._ws_tokens:
            self._ws_feed._ws_instruments = dict(self._ws_tokens)  # noqa: SLF001
            self._ws_feed.start()

    # -- HTTP helpers -----------------------------------------------------

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}" if path.startswith("/") else path
        cache_key = f"{path}?{sorted((params or {}).items())}"
        now = time.monotonic()
        cached = self._rest_cache.get(cache_key)
        if cached and (now - cached[0]) < self.cache_ttl_seconds:
            return cached[1]

        try:
            resp = self._client.get(url, headers=self._headers, params=params)
        except httpx.HTTPError as exc:
            raise ProviderError(f"INDstocks request failed for {path}: {exc}") from exc

        if resp.status_code in (401, 403):
            self._warn_auth_once(path, resp.status_code)
            raise ProviderAuthError(
                "INDstocks access token rejected (expired or invalid) on "
                f"{path}: HTTP {resp.status_code}. Regenerate at "
                "https://indstocks.com/app/api-trading/access-tokens"
            )
        if resp.status_code != 200:
            raise ProviderError(
                f"INDstocks {path} returned HTTP {resp.status_code}: {resp.text[:200]}"
            )
        try:
            payload = resp.json()
        except Exception as exc:
            raise ProviderError(f"INDstocks {path} returned non-JSON: {exc}") from exc

        self._rest_cache[cache_key] = (now, payload)
        return payload

    def _warn_auth_once(self, context: str, status: int) -> None:
        """Log the token-expiry remediation ONCE — never per request."""
        if self._auth_warned:
            return
        self._auth_warned = True
        logger.error(
            "INDstocks authentication failed (HTTP %s on %s). The access token is "
            "expired, incorrect, or revoked — generate a fresh 24h token at "
            "https://indstocks.com/app/api-trading/access-tokens, update "
            "INDSTOCKS_ACCESS_TOKEN in .env, and restart run_live.ps1. REST calls "
            "fail softly until then; VIX/breadth/candles still come from the NSE "
            "fallback.",
            status,
            context,
        )

    def _get_csv(self, path: str, params: dict[str, str] | None = None) -> list[list[str]]:
        url = f"{self.base_url}{path}" if path.startswith("/") else path
        try:
            resp = self._client.get(url, headers=self._headers, params=params)
        except httpx.HTTPError as exc:
            raise ProviderError(f"INDstocks CSV request failed for {path}: {exc}") from exc
        if resp.status_code in (401, 403):
            self._warn_auth_once(path, resp.status_code)
            raise ProviderAuthError(
                "INDstocks access token rejected (expired or invalid) on "
                f"{path}: HTTP {resp.status_code}. Regenerate at "
                "https://indstocks.com/app/api-trading/access-tokens"
            )
        if resp.status_code != 200:
            raise ProviderError(
                f"INDstocks {path} returned HTTP {resp.status_code}: {resp.text[:200]}"
            )
        reader = csv.reader(io.StringIO(resp.text))
        return list(reader)

    def _bootstrap_instruments(self) -> None:
        """Load index SECURITY_IDs and WebSocket tokens from instruments master."""
        try:
            rows = self._get_csv("/market/instruments", params={"source": "index"})
        except ProviderAuthError:
            # _warn_auth_once already logged the remediation; keep the
            # provider usable on default scrips (all REST calls will 403).
            self._apply_default_scrips()
            return
        except ProviderError as exc:
            logger.warning("Could not load INDstocks index instruments: %s", exc)
            self._apply_default_scrips()
            return

        # Index CSV: EXCH, name, SECURITY_ID (positional — header is misleading)
        name_to_scrip: dict[str, str] = {}
        for row in rows[1:] if len(rows) > 1 else rows:
            if len(row) < 3:
                continue
            index_name = row[1].strip().upper()
            scrip = row[2].strip()
            name_to_scrip[index_name] = scrip

        for symbol, aliases in SYMBOL_INDEX_NAMES.items():
            prefix = "BIDX:" if symbol == "SENSEX" else "NIDX:"
            for alias in aliases:
                scrip = name_to_scrip.get(alias.upper())
                if scrip:
                    self._index_scrips[symbol] = scrip
                    self._ws_tokens[symbol] = f"{prefix}{scrip}"
                    break

        if "NIFTY" not in self._index_scrips:
            self._apply_default_scrips()

        logger.info(
            "INDstocks instruments loaded: %s",
            ", ".join(f"{s}={self._index_scrips[s]}" for s in sorted(self._index_scrips)),
        )

    def _apply_default_scrips(self) -> None:
        """Known fallbacks when instruments CSV is unavailable."""
        defaults = {
            "NIFTY": ("40000001", "NIDX:40000001"),
            "BANKNIFTY": ("40000003", "NIDX:40000003"),
            "FINNIFTY": ("40000100", "NIDX:40000100"),
            "SENSEX": ("40000006", "BIDX:40000006"),
        }
        for symbol, (scrip, ws_token) in defaults.items():
            self._index_scrips.setdefault(symbol, scrip)
            self._ws_tokens.setdefault(symbol, ws_token)

    def _nse(self) -> NSEMarketDataProvider:
        if self._nse_fallback is None:
            self._nse_fallback = NSEMarketDataProvider(timeout_seconds=self.timeout_seconds)
        return self._nse_fallback

    def _underlying_scrip(self, symbol: str) -> str:
        sym = symbol.upper().strip()
        scrip = self._index_scrips.get(sym)
        if not scrip:
            raise ProviderError(
                f"Unknown symbol {symbol!r} for INDstocks — not found in index instruments"
            )
        return scrip

    def _quote_scrip_code(self, symbol: str) -> str:
        return f"NIDX_{self._underlying_scrip(symbol)}"

    def _fetch_full_quote_rest(self, symbol: str) -> dict[str, Any]:
        scrip_code = self._quote_scrip_code(symbol)
        payload = self._get_json("/market/quotes/full", params={"scrip-codes": scrip_code})
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or scrip_code not in data:
            raise ProviderError(f"No INDstocks quote returned for {symbol!r} ({scrip_code})")
        return data[scrip_code]

    # -- MarketDataProvider -----------------------------------------------

    def get_quote(self, symbol: str) -> RawPayload:
        """Return a live index quote, preferring WebSocket LTP when fresh."""
        sym = symbol.upper().strip()
        ts = now_ist()
        rest: dict[str, Any] = {}

        try:
            rest = self._fetch_full_quote_rest(sym)
        except ProviderError as exc:
            logger.debug("INDstocks REST quote failed for %s: %s", sym, exc)

        ws_ltp = self._quote_cache.get(sym, max_age_seconds=30.0)
        last_price = ws_ltp
        if last_price is None:
            if rest:
                last_price = float(rest.get("live_price", 0.0))
            else:
                # Last resort: underlying LTP from option chain
                chain = self.get_option_chain(sym)
                last_price = float(chain.get("spot_price", 0.0))
        elif rest:
            # Merge WS LTP with REST OHLC/bid-ask
            pass

        if not last_price or last_price <= 0:
            raise ProviderError(f"Could not obtain live price for {sym!r}")

        prev_close = float(rest.get("prev_close", last_price) if rest else last_price)
        open_price = float(rest.get("day_open", last_price) if rest else last_price)
        high_price = float(rest.get("day_high", last_price) if rest else last_price)
        low_price = float(rest.get("day_low", last_price) if rest else last_price)
        volume = int(rest.get("volume", 0) if rest else 0)

        depth = rest.get("market_depth") if rest else None
        bid = ask = last_price
        bid_size = ask_size = 1000
        if isinstance(depth, dict):
            levels = depth.get("depth") or []
            if levels:
                buy = levels[0].get("buy") or {}
                sell = levels[0].get("sell") or {}
                if buy.get("price"):
                    bid = float(str(buy["price"]).replace(",", ""))
                    bid_size = int(float(str(buy.get("quantity", 1000)).replace(",", "")))
                if sell.get("price"):
                    ask = float(str(sell["price"]).replace(",", ""))
                    ask_size = int(float(str(sell.get("quantity", 1000)).replace(",", "")))

        if bid == ask == last_price:
            spread = 0.05
            bid = round(last_price - spread, 2)
            ask = round(last_price + spread, 2)

        return {
            "symbol": sym,
            "timestamp": ts.isoformat(),
            "bid": bid,
            "ask": ask,
            "last_price": last_price,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "volume": volume,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "previous_close": prev_close,
            "source": "websocket" if ws_ltp is not None else "rest",
        }

    def get_option_chain(
        self, symbol: str, expiry_date: datetime | date | None = None
    ) -> RawPayload:
        sym = symbol.upper().strip()
        scrip = self._underlying_scrip(sym)
        expiries = self._discover_expiries(sym)
        if not expiries:
            raise ProviderError(f"No option expiries found for {sym!r}")

        target_expiry = self._resolve_expiry(expiry_date, expiries)
        payload = self._get_json(
            "/market/option-chain",
            params={
                "exchange": "NSE",
                "segment": "INDEX",
                "underlying-scrip": scrip,
                "expiry": target_expiry,
                "strike_count": self.strike_count,
            },
        )
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ProviderError(f"Invalid option chain response for {sym!r}")

        spot_price = float(data.get("underlying_ltp", 0.0))
        strikes = data.get("strikes") or {}
        entries: list[dict[str, Any]] = []

        for strike_key, legs in strikes.items():
            if not isinstance(legs, dict):
                continue
            try:
                strike = float(strike_key)
            except (TypeError, ValueError):
                continue
            for opt_type, leg_key in (("call", "ce"), ("put", "pe")):
                leg = legs.get(leg_key)
                if not isinstance(leg, dict):
                    continue
                oi = int(leg.get("oi", 0))
                prev_oi = int(leg.get("previous_oi", oi))
                iv_raw = leg.get("iv")
                iv = round(float(iv_raw) / 100.0, 4) if iv_raw is not None else 0.0
                entries.append(
                    {
                        "strike": strike,
                        "option_type": opt_type,
                        "open_interest": oi,
                        "change_in_oi": oi - prev_oi,
                        "price_change_pct": 0.0,
                        "last_price": float(leg.get("last_price", 0.0)),
                        "bid": float(leg.get("top_bid_price", 0.0)),
                        "ask": float(leg.get("top_ask_price", 0.0)),
                        "iv": iv,
                    }
                )

        if not entries:
            raise ProviderError(f"Empty option chain for {sym!r} expiry {target_expiry}")

        expiry_dt = datetime.strptime(target_expiry, "%Y-%m-%d").replace(
            hour=15, minute=30, tzinfo=IST
        )
        ts = now_ist()
        if expiry_dt <= ts:
            expiry_dt = ts + timedelta(hours=1)

        return {
            "underlying_symbol": sym,
            "timestamp": ts.isoformat(),
            "spot_price": spot_price,
            "expiry_date": expiry_dt.isoformat(),
            "entries": entries,
        }

    def get_candles(
        self, symbol: str, lookback_days: int = 30, timeframe: str = "1d"
    ) -> list[RawPayload]:
        sym = symbol.upper().strip()
        interval_map = {"1d": "1day", "1day": "1day", "1m": "1minute", "5m": "5minute"}
        interval = interval_map.get(timeframe, "1day")
        scrip_code = self._quote_scrip_code(sym)

        end = now_ist()
        start = end - timedelta(days=max(lookback_days + 15, 60))
        params = {
            "scrip-codes": scrip_code,
            "start_time": int(start.timestamp() * 1000),
            "end_time": int(end.timestamp() * 1000),
        }
        try:
            payload = self._get_json(f"/market/historical/{interval}", params=params)
        except ProviderError:
            return self._nse().get_candles(sym, lookback_days, timeframe)

        block = (payload.get("data") or {}).get(scrip_code) if isinstance(payload, dict) else None
        raw_candles = block.get("candles") if isinstance(block, dict) else None
        if not raw_candles:
            return self._nse().get_candles(sym, lookback_days, timeframe)

        candles: list[RawPayload] = []
        for bar in raw_candles:
            ts_epoch = bar.get("ts")
            if ts_epoch is None:
                continue
            dt = datetime.fromtimestamp(int(ts_epoch), tz=IST)
            o = round(float(bar["o"]), 2)
            h = round(float(bar["h"]), 2)
            l = round(float(bar["l"]), 2)
            c = round(float(bar["c"]), 2)
            candles.append(
                {
                    "symbol": sym,
                    "timestamp": dt.isoformat(),
                    "open": o,
                    "high": max(h, o, c),
                    "low": min(l, o, c),
                    "close": c,
                    "volume": int(bar.get("v", 0)),
                }
            )
        candles.sort(key=lambda c: c["timestamp"])
        return candles[-lookback_days:]

    def get_futures_data(self, symbol: str) -> RawPayload:
        sym = symbol.upper().strip()
        lot = self._lot_sizes.get(sym, 50)
        quote = self.get_quote(sym)
        exp = now_ist() + timedelta(days=7)
        return {
            "contract": {
                "symbol": f"{sym}FUT",
                "name": f"{sym} Current Month Futures",
                "underlying_symbol": sym,
                "expiry_date": exp.isoformat(),
                "contract_size": lot,
                "lot_size": lot,
                "tick_size": 0.05,
            },
            "quote": quote,
        }

    def get_market_breadth(self) -> RawPayload:
        return self._nse().get_market_breadth()

    def get_vix(self) -> RawPayload:
        return self._nse().get_vix()

    def get_fii_dii_data(self) -> RawPayload:
        return self._nse().get_fii_dii_data()

    # -- expiry discovery -------------------------------------------------

    def _discover_expiries(self, symbol: str) -> list[str]:
        sym = symbol.upper()
        now = time.monotonic()
        cached = self._expiry_cache.get(sym)
        if cached and (now - cached[0]) < 3600:
            return cached[1]

        fno_name = SYMBOL_FNO_NAMES.get(sym, sym)
        expiries: set[str] = set()

        # 1. Try official /market/instruments/expiries API endpoint
        try:
            payload = self._get_json(
                "/market/instruments/expiries",
                params={"exchange": "NSE", "segment": "DERIVATIVE", "underlying": fno_name},
            )
            if isinstance(payload, dict) and isinstance(payload.get("data"), list):
                for raw_exp in payload["data"]:
                    parsed = self._parse_expiry_date(str(raw_exp))
                    if parsed:
                        expiries.add(parsed)
        except Exception as exc:
            logger.debug("INDstocks expiries endpoint failed for %s: %s", sym, exc)

        # 2. Fallback to FNO instruments CSV if needed
        if not expiries:
            try:
                rows = self._get_csv("/market/instruments", params={"source": "fno"})
                header = [h.strip().upper() for h in rows[0]] if rows else []
                sym_idx = header.index("SYMBOL_NAME") if "SYMBOL_NAME" in header else 8
                exp_idx = header.index("EXPIRY_DATE") if "EXPIRY_DATE" in header else 9
                lot_idx = header.index("LOT_UNITS") if "LOT_UNITS" in header else 6

                for row in rows[1:]:
                    if len(row) <= max(sym_idx, exp_idx):
                        continue
                    if row[sym_idx].strip().upper() != fno_name:
                        continue
                    raw_exp = row[exp_idx].strip()
                    parsed = self._parse_expiry_date(raw_exp)
                    if parsed:
                        expiries.add(parsed)
                    if len(row) > lot_idx and row[lot_idx].strip().isdigit():
                        self._lot_sizes.setdefault(sym, int(row[lot_idx].strip()))
            except ProviderError as exc:
                logger.warning("FNO instruments fetch failed for %s: %s", sym, exc)

        if not expiries:
            # Rolling weekly fallback: next four Tuesdays
            today = now_ist().date()
            for offset in range(1, 29):
                candidate = today + timedelta(days=offset)
                if candidate.weekday() == 1:  # Tuesday — common NIFTY weekly expiry
                    expiries.add(candidate.strftime("%Y-%m-%d"))
                if len(expiries) >= 4:
                    break

        ordered = sorted(expiries)
        self._expiry_cache[sym] = (now, ordered)
        return ordered

    @staticmethod
    def _parse_expiry_date(raw: str) -> str | None:
        raw = raw.strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%d-%b-%y"):
            try:
                return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    @staticmethod
    def _resolve_expiry(
        expiry_date: datetime | date | None, available: list[str]
    ) -> str:
        if not available:
            raise ProviderError("No expiries available")
        if expiry_date is None:
            return available[0]
        target = (
            expiry_date.date() if isinstance(expiry_date, datetime) else expiry_date
        ).strftime("%Y-%m-%d")
        if target in available:
            return target
        return available[0]
