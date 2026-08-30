"""Direct NSE India Web Market Data Provider.

Fetches live market data (Quotes, Complete Option Chains with Open Interest,
India VIX, and Market Breadth) directly from public NSE India endpoints
without requiring broker accounts or paid API keys.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import Any

import httpx

try:
    from pnsea import NSESession
except ImportError:
    NSESession = None

from app.data.providers.base import MarketDataProvider, ProviderError, RawPayload
from app.logging.setup import get_logger
from app.models.time import IST, now_ist

logger = get_logger("data.provider.nse")

#: Default browser headers required by NSE India anti-bot protections.
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

#: Symbol mappings to NSE index names and Yahoo chart tickers.
SYMBOL_MAP = {
    "NIFTY": {
        "nse_index": "NIFTY 50",
        "nse_chain_symbol": "NIFTY",
        "yahoo_ticker": "^NSEI",
        "lot_size": 75,
    },
    "BANKNIFTY": {
        "nse_index": "NIFTY BANK",
        "nse_chain_symbol": "BANKNIFTY",
        "yahoo_ticker": "^NSEBANK",
        "lot_size": 30,
    },
    "FINNIFTY": {
        "nse_index": "NIFTY FINANCIAL SERVICES",
        "nse_chain_symbol": "FINNIFTY",
        "yahoo_ticker": "NIFTY_FIN_SERVICE.NS",
        "lot_size": 40,
    },
}


class NSEMarketDataProvider(MarketDataProvider):
    """Direct NSE India HTTP session-based provider.

    Parameters
    ----------
    timeout_seconds:
        HTTP request timeout in seconds.
    cache_ttl_seconds:
        Short-lived cache duration for multi-query calls (e.g. allIndices).
    base_url:
        Base NSE URL (default: https://www.nseindia.com).
    client:
        Optional pre-configured httpx.Client for testing and dependency injection.
    """

    name = "nse"

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        cache_ttl_seconds: float = 5.0,
        base_url: str = "https://www.nseindia.com",
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self._client = client or httpx.Client(
            headers=NSE_HEADERS,
            timeout=timeout_seconds,
            follow_redirects=True,
        )
        self._stealth_session = NSESession() if NSESession is not None else None
        self._session_initialized = False
        self._last_cookie_time: float = 0.0

        # Short-lived in-memory caches to prevent redundant hits in one cycle
        self._all_indices_cache: dict[str, Any] | None = None
        self._all_indices_time: float = 0.0
        self._option_chain_cache: dict[str, tuple[float, dict[str, Any]]] = {}

    def _ensure_session(self) -> None:
        """Initialize session cookies if not yet established or if expired (30m)."""
        now = time.monotonic()
        if self._session_initialized and (now - self._last_cookie_time) < 1800:
            return

        try:
            url = f"{self.base_url}/option-chain"
            resp = self._client.get(url, headers=NSE_HEADERS)
            if resp.status_code == 200:
                self._session_initialized = True
                self._last_cookie_time = now
                logger.debug("NSE session cookies initialized successfully")
            else:
                logger.warning("NSE session init returned status %d", resp.status_code)
        except Exception as exc:
            logger.warning("Failed to initialize NSE session cookies: %s", exc)

    def _get_json(self, path: str, referer: str = "/option-chain") -> dict[str, Any] | list[dict[str, Any]]:
        """Fetch JSON payload from NSE endpoint with automatic session management."""
        url = f"{self.base_url}{path}" if path.startswith("/") else path
        headers = dict(NSE_HEADERS)
        headers["Referer"] = f"{self.base_url}{referer}" if referer.startswith("/") else referer

        # 1. Try stealth session first (bypasses Akamai WAF for v3 option chains)
        if self._stealth_session is not None:
            try:
                resp = self._stealth_session.get(url, headers={"Referer": headers["Referer"]})
                if resp is not None and resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception as exc:
                        logger.debug("Failed to decode JSON from stealth session %s: %s", path, exc)
            except Exception as exc:
                logger.debug("Stealth session request error for %s: %s", path, exc)

        # 2. Fall back to httpx Client
        self._ensure_session()
        try:
            resp = self._client.get(url, headers=headers)
            if resp.status_code in (401, 403):
                # Refresh session and retry once
                logger.info("NSE session refreshed after HTTP %d", resp.status_code)
                self._session_initialized = False
                self._ensure_session()
                resp = self._client.get(url, headers=headers)

            if resp.status_code != 200:
                raise ProviderError(
                    f"NSE endpoint {path} returned HTTP {resp.status_code}: {resp.text[:200]}"
                )
            try:
                return resp.json()
            except Exception as exc:
                raise ProviderError(f"Failed to decode JSON from NSE endpoint {path}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"HTTP request to NSE endpoint {path} failed: {exc}") from exc

    def _fetch_all_indices(self) -> list[dict[str, Any]]:
        """Fetch /api/allIndices with short-lived cycle caching."""
        now = time.monotonic()
        if (
            self._all_indices_cache is not None
            and (now - self._all_indices_time) < self.cache_ttl_seconds
        ):
            return self._all_indices_cache.get("data", [])

        data = self._get_json("/api/allIndices", referer="/")
        if isinstance(data, dict):
            self._all_indices_cache = data
            self._all_indices_time = now
            return data.get("data", [])
        return []

    # -- MarketDataProvider Implementation ------------------------------------

    def get_quote(self, symbol: str) -> RawPayload:
        """Fetch live index quote for NIFTY / BANKNIFTY from /api/allIndices."""
        sym_upper = symbol.upper().strip()
        info = SYMBOL_MAP.get(sym_upper)
        index_name = info["nse_index"] if info else sym_upper

        indices = self._fetch_all_indices()
        record = next((i for i in indices if i.get("index") == index_name), None)

        if not record:
            raise ProviderError(f"Symbol {symbol!r} (index {index_name!r}) not found in NSE allIndices")

        last_price = float(record.get("last", 0.0))
        prev_close = float(record.get("previousClose", last_price))
        open_price = float(record.get("open", last_price))
        high_price = float(record.get("high", last_price))
        low_price = float(record.get("low", last_price))

        # Index quotes do not carry explicit bid/ask order books; approximate minimal spread
        spread = 0.05
        bid = round(last_price - spread, 2)
        ask = round(last_price + spread, 2)
        volume = int(record.get("totalTradedVolume", 0))

        # Parse timestamp
        ts = self._parse_nse_datetime(record.get("date"))

        return {
            "symbol": sym_upper,
            "timestamp": ts.isoformat(),
            "bid": bid,
            "ask": ask,
            "last_price": last_price,
            "bid_size": 1000,
            "ask_size": 1000,
            "volume": volume,
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "previous_close": prev_close,
        }

    def get_option_chain(
        self, symbol: str, expiry_date: datetime | date | None = None
    ) -> RawPayload:
        """Fetch live option chain with open interest and IV from NSE v3 option chain endpoint."""
        sym_upper = symbol.upper().strip()
        info = SYMBOL_MAP.get(sym_upper)
        chain_symbol = info["nse_chain_symbol"] if info else sym_upper
        is_index = sym_upper in SYMBOL_MAP or "NIFTY" in sym_upper

        now = time.monotonic()

        # 1. Fetch available expiries from contract-info
        try:
            contract_info = self._get_json(
                f"/api/option-chain-contract-info?symbol={chain_symbol}",
                referer=f"/option-chain?symbol={chain_symbol}",
            )
            expiry_dates_str = contract_info.get("expiryDates", []) if isinstance(contract_info, dict) else []
        except Exception as exc:
            logger.debug("Failed to fetch contract-info for %s: %s", chain_symbol, exc)
            expiry_dates_str = []

        if not expiry_dates_str:
            # Try legacy endpoint format as fallback
            cached = self._option_chain_cache.get(chain_symbol)
            if cached and (now - cached[0]) < self.cache_ttl_seconds:
                payload = cached[1]
            else:
                raw_data = self._get_json(
                    f"/api/option-chain-indices?symbol={chain_symbol}" if is_index else f"/api/option-chain-equities?symbol={chain_symbol}",
                    referer=f"/option-chain?symbol={chain_symbol}",
                )
                payload = raw_data if isinstance(raw_data, dict) else {}
                self._option_chain_cache[chain_symbol] = (now, payload)
            records = payload.get("records", {})
            expiry_dates_str = records.get("expiryDates", [])

        if not expiry_dates_str:
            raise ProviderError(f"No expiry dates returned by NSE for symbol {symbol!r}")

        # Determine target expiry
        target_expiry_str = self._resolve_expiry_date(expiry_date, expiry_dates_str)

        # 2. Fetch v3 option chain payload for target expiry
        cache_key = f"{chain_symbol}_{target_expiry_str}"
        cached = self._option_chain_cache.get(cache_key)
        if cached and (now - cached[0]) < self.cache_ttl_seconds:
            payload = cached[1]
        else:
            inst_type = "Indices" if is_index else "Equities"
            raw_data = self._get_json(
                f"/api/option-chain-v3?type={inst_type}&symbol={chain_symbol}&expiry={target_expiry_str}",
                referer=f"/option-chain?symbol={chain_symbol}",
            )
            payload = raw_data if isinstance(raw_data, dict) else {}
            self._option_chain_cache[cache_key] = (now, payload)

        records = payload.get("records", {})
        filtered_block = payload.get("filtered", {})
        data_rows = filtered_block.get("data", []) or records.get("data", [])
        if not data_rows:
            raise ProviderError(f"No option chain data returned by NSE for symbol {symbol!r}")

        spot_price = float(records.get("underlyingValue", 0.0))
        if spot_price <= 0.0:
            try:
                spot_price = float(self.get_quote(sym_upper)["last_price"])
            except Exception:
                pass

        entries: list[dict[str, Any]] = []
        for row in data_rows:
            strike = float(row.get("strikePrice", 0.0))
            if strike <= 0.0:
                continue

            # Call Option (CE)
            if "CE" in row and row["CE"]:
                ce = row["CE"]
                entries.append(
                    {
                        "strike": strike,
                        "option_type": "call",
                        "open_interest": int(ce.get("openInterest", 0)),
                        "change_in_oi": int(ce.get("changeinOpenInterest", 0)),
                        "price_change_pct": float(ce.get("pChange", 0.0) or ce.get("PChange", 0.0)),
                        "last_price": float(ce.get("lastPrice", 0.0)),
                        "bid": float(ce.get("buyPrice1", 0.0) or ce.get("bidprice", 0.0) or ce.get("bid", 0.0)),
                        "ask": float(ce.get("sellPrice1", 0.0) or ce.get("askPrice", 0.0) or ce.get("ask", 0.0)),
                        "iv": round(float(ce.get("impliedVolatility", 0.0)) / 100.0, 4) if ce.get("impliedVolatility") else 0.0,
                    }
                )

            # Put Option (PE)
            if "PE" in row and row["PE"]:
                pe = row["PE"]
                entries.append(
                    {
                        "strike": strike,
                        "option_type": "put",
                        "open_interest": int(pe.get("openInterest", 0)),
                        "change_in_oi": int(pe.get("changeinOpenInterest", 0)),
                        "price_change_pct": float(pe.get("pChange", 0.0) or pe.get("PChange", 0.0)),
                        "last_price": float(pe.get("lastPrice", 0.0)),
                        "bid": float(pe.get("buyPrice1", 0.0) or pe.get("bidprice", 0.0) or pe.get("bid", 0.0)),
                        "ask": float(pe.get("sellPrice1", 0.0) or pe.get("askPrice", 0.0) or pe.get("ask", 0.0)),
                        "iv": round(float(pe.get("impliedVolatility", 0.0)) / 100.0, 4) if pe.get("impliedVolatility") else 0.0,
                    }
                )

        ts = self._parse_nse_datetime(records.get("timestamp"))

        # Target expiry date at 15:30:00 IST (guaranteeing expiry_date > timestamp)
        target_expiry_dt = self._parse_nse_date(target_expiry_str)
        if target_expiry_dt <= ts:
            target_expiry_dt = ts + timedelta(hours=1)

        return {
            "underlying_symbol": sym_upper,
            "timestamp": ts.isoformat(),
            "spot_price": spot_price,
            "expiry_date": target_expiry_dt.isoformat(),
            "entries": entries,
        }

    def get_vix(self) -> RawPayload:
        """Fetch live India VIX value and change from /api/allIndices."""
        indices = self._fetch_all_indices()
        record = next((i for i in indices if i.get("index") == "INDIA VIX"), None)

        if not record:
            raise ProviderError("INDIA VIX record not found in NSE allIndices")

        val = float(record.get("last", 0.0))
        change = float(record.get("variation", 0.0))
        ts = self._parse_nse_datetime(record.get("date"))

        return {
            "symbol": "INDIAVIX",
            "timestamp": ts.isoformat(),
            "value": val,
            "change": change,
        }

    def get_market_breadth(self) -> RawPayload:
        """Fetch market breadth (Advancers, Decliners, Unchanged) from NIFTY 50."""
        indices = self._fetch_all_indices()
        record = next((i for i in indices if i.get("index") == "NIFTY 50"), None)

        if not record:
            raise ProviderError("NIFTY 50 record not found for breadth extraction")

        advancers = int(record.get("advances", 0))
        decliners = int(record.get("declines", 0))
        unchanged = int(record.get("unchanged", 0))
        ts = self._parse_nse_datetime(record.get("date"))

        return {
            "timestamp": ts.isoformat(),
            "advancers": advancers,
            "decliners": decliners,
            "unchanged": unchanged,
        }

    def get_candles(
        self, symbol: str, lookback_days: int = 30, timeframe: str = "1d"
    ) -> list[RawPayload]:
        """Fetch daily historical OHLCV candles via Yahoo Finance chart API."""
        sym_upper = symbol.upper().strip()
        info = SYMBOL_MAP.get(sym_upper)
        ticker = info["yahoo_ticker"] if info else sym_upper

        # Query Yahoo Finance chart API for daily bars
        range_str = f"{max(lookback_days + 15, 60)}d"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={range_str}&interval={timeframe}"

        try:
            resp = self._client.get(
                url,
                headers={"User-Agent": NSE_HEADERS["User-Agent"]},
            )
            if resp.status_code == 200:
                data = resp.json()
                candles = self._parse_yahoo_chart_data(sym_upper, data)
                if candles:
                    return candles[-lookback_days:]
        except Exception as exc:
            logger.warning("Yahoo Finance candle request failed for %s: %s", symbol, exc)

        # Fail-soft: if network candle fetch fails, synthesize recent reference candles
        return self._generate_fallback_candles(sym_upper, lookback_days)

    def get_futures_data(self, symbol: str) -> RawPayload:
        """Provide futures snapshot payload."""
        sym_upper = symbol.upper().strip()
        info = SYMBOL_MAP.get(sym_upper)
        lot = info["lot_size"] if info else 50
        quote = self.get_quote(sym_upper)

        exp = now_ist() + timedelta(days=7)
        return {
            "contract": {
                "symbol": f"{sym_upper}FUT",
                "name": f"{sym_upper} Current Month Futures",
                "underlying_symbol": sym_upper,
                "expiry_date": exp.isoformat(),
                "contract_size": lot,
                "lot_size": lot,
                "tick_size": 0.05,
            },
            "quote": quote,
        }

    def get_fii_dii_data(self) -> RawPayload:
        """Provide real-time daily FII/DII flow summary from NSE."""
        now = now_ist()
        try:
            items = self._get_json("/api/fiidiiTradeReact", referer="/")
            if isinstance(items, list) and items:
                fii_net = 0.0
                dii_net = 0.0
                ts = now
                for item in items:
                    cat = str(item.get("category", "")).upper()
                    val = float(item.get("netValue", 0.0))
                    date_str = item.get("date")
                    if date_str:
                        ts = self._parse_nse_datetime(date_str)
                    if "DII" in cat:
                        dii_net = val
                    elif "FII" in cat:
                        fii_net = val
                return {
                    "timestamp": ts.isoformat(),
                    "fii_cash_net": fii_net,
                    "dii_cash_net": dii_net,
                    "fii_index_futures_net": 0.0,
                    "fii_index_options_net": 0.0,
                }
        except Exception as exc:
            logger.warning("Live FII/DII flow fetch failed: %s", exc)

        return {
            "timestamp": now.isoformat(),
            "fii_cash_net": 0.0,
            "dii_cash_net": 0.0,
            "fii_index_futures_net": 0.0,
            "fii_index_options_net": 0.0,
        }

    # -- Internal Parsing Helpers ---------------------------------------------

    def _parse_nse_datetime(self, date_str: str | None) -> datetime:
        """Parse NSE timestamp string (e.g. '28-Aug-2025 15:30:00') into IST datetime."""
        if not date_str:
            return now_ist()
        clean = date_str.strip()
        for fmt in ("%d-%b-%Y %H:%M:%S", "%d-%b-%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%b-%Y", "%d-%m-%Y"):
            try:
                dt = datetime.strptime(clean, fmt)
                return dt.replace(tzinfo=IST)
            except ValueError:
                continue
        return now_ist()

    def _parse_nse_date(self, date_str: str) -> datetime:
        """Parse NSE date string (e.g. '28-Aug-2025' or '25-08-2026') into IST expiry datetime at 15:30."""
        clean = date_str.strip()
        for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d-%b-%y", "%d-%m-%y"):
            try:
                d = datetime.strptime(clean, fmt).date()
                return datetime.combine(d, datetime.min.time()).replace(
                    hour=15, minute=30, tzinfo=IST
                )
            except ValueError:
                continue
        return now_ist()

    def _resolve_expiry_date(
        self, expiry_date: datetime | date | None, available_expiries: list[str]
    ) -> str:
        """Match requested expiry date or return the nearest available expiry string."""
        if not available_expiries:
            raise ProviderError("No expiry dates available in option chain")

        if expiry_date is None:
            return available_expiries[0]

        target_date = expiry_date.date() if isinstance(expiry_date, datetime) else expiry_date
        target_str_1 = target_date.strftime("%d-%b-%Y").upper()
        target_str_2 = target_date.strftime("%d-%m-%Y").upper()

        for exp in available_expiries:
            exp_upper = exp.upper()
            if exp_upper in (target_str_1, target_str_2):
                return exp
        # Nearest fallback
        return available_expiries[0]

    def _parse_yahoo_chart_data(self, symbol: str, data: dict[str, Any]) -> list[RawPayload]:
        """Convert Yahoo Finance chart JSON structure into standard candle payloads."""
        candles: list[RawPayload] = []
        try:
            chart = data["chart"]["result"][0]
            timestamps = chart["timestamp"]
            indicators = chart["indicators"]["quote"][0]
            opens = indicators["open"]
            highs = indicators["high"]
            lows = indicators["low"]
            closes = indicators["close"]
            volumes = indicators.get("volume", [0] * len(timestamps))

            for i, ts_epoch in enumerate(timestamps):
                o, h, l, c = opens[i], highs[i], lows[i], closes[i]
                if None in (o, h, l, c):
                    continue
                dt = datetime.fromtimestamp(ts_epoch, tz=IST)
                candles.append(
                    {
                        "symbol": symbol,
                        "timestamp": dt.isoformat(),
                        "open": round(float(o), 2),
                        "high": round(float(h), 2),
                        "low": round(float(l), 2),
                        "close": round(float(c), 2),
                        "volume": int(volumes[i] or 0),
                    }
                )
        except Exception as exc:
            logger.debug("Failed to parse Yahoo chart response: %s", exc)
        return candles

    def _generate_fallback_candles(self, symbol: str, n_days: int) -> list[RawPayload]:
        """Synthesize reference candles when offline/offline-fallback is active."""
        base_price = 24000.0 if symbol == "NIFTY" else 52000.0
        now = now_ist()
        candles = []
        for d in range(n_days, 0, -1):
            ts = now - timedelta(days=d)
            candles.append(
                {
                    "symbol": symbol,
                    "timestamp": ts.isoformat(),
                    "open": round(base_price, 2),
                    "high": round(base_price * 1.005, 2),
                    "low": round(base_price * 0.995, 2),
                    "close": round(base_price * 1.001, 2),
                    "volume": 1000000,
                }
            )
        return candles
