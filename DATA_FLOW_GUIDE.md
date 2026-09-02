# Data Flow & Real-Time Architecture Guide

> **Understanding how market data flows through MarketAgent (for non-traders and engineers)**

---

## High-Level Data Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL DATA SOURCES                        │
│                                                                  │
│  ┌──────────────────────┐  ┌──────────────────────┐            │
│  │   INDstocks API      │  │   NSE Public API     │            │
│  │ (REST + WebSocket)   │  │ (REST API)           │            │
│  └──────────┬───────────┘  └──────────┬───────────┘            │
│             │                         │                         │
│  ▪ Quotes   │                  ▪ Breadth                       │
│  ▪ Option   │                  ▪ VIX                           │
│    chains   │                  ▪ FII/DII flows                │
│  ▪ Candles  │                                                  │
└─────────────┼─────────────────────┬───────────────────────────┘
              │                     │
              └─────────────┬───────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│        MARKET DATA PROVIDER LAYER                               │
│        (File: app/data/providers/*.py)                          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ INDstocksMarketDataProvider                              │  │
│  │  ▪ Fetch quotes via REST                                │  │
│  │  ▪ Fetch option chains                                  │  │
│  │  ▪ Keep WebSocket alive for live LTPs                   │  │
│  │  ▪ Cache prices in background thread                    │  │
│  │  ▪ Handle auth errors & reconnect                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ NSEMarketDataProvider                                    │  │
│  │  ▪ Fetch breadth (stocks up/down)                       │  │
│  │  ▪ Fetch VIX (volatility index)                         │  │
│  │  ▪ Fetch FII/DII flows                                  │  │
│  │  ▪ Public URLs (no auth needed)                         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│     NORMALIZER LAYER (app/data/normalizers/)                    │
│     Convert API JSON → Pydantic models                          │
│                                                                  │
│  Raw INDstocks Response:                                        │
│  {                                                              │
│    "symbol": "NIFTY",                                          │
│    "ltp": "25432.45",                                          │
│    "bid": "25431.00",                                          │
│    "ask": "25433.00",                                          │
│    "timestamp": "1694001000000"                                │
│  }                                                              │
│            │                                                    │
│            ▼ MarketDataNormalizer.normalize_quote()            │
│            │                                                    │
│  Normalized Model:                                              │
│  Quote(                                                         │
│    symbol="NIFTY",                                            │
│    ltp=25432.45,                                              │
│    bid=25431.00,                                              │
│    ask=25433.00,                                              │
│    timestamp=datetime(2023, 9, 6, 10, 30, 0, tzinfo=IST),   │
│    source="indstocks"                                         │
│  )                                                             │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│     VALIDATOR LAYER (app/data/validators/)                      │
│     Check data quality (VALID/WARNING/INVALID)                  │
│                                                                  │
│  Checks:                                                        │
│  ✓ Price > 0?                                                  │
│  ✓ Bid < Ask?                                                  │
│  ✓ Timestamp is recent (< 2 min old)?                          │
│  ✓ OI change is reasonable (< 50% change)?                     │
│  ✓ No obvious data corruption?                                 │
│                                                                  │
│  Report: DataQualityReport                                      │
│  {                                                              │
│    "status": "VALID",       # or WARNING or INVALID            │
│    "warnings": [],                                              │
│    "age_seconds": 15,                                          │
│    "message": "Quote is fresh and valid"                       │
│  }                                                              │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│     MARKET DATA COLLECTOR (app/data/collectors/)                │
│     Orchestrates provider → normalizer → validator              │
│     Produces: MarketSnapshot                                    │
│                                                                  │
│  For each symbol:                                               │
│  1. Get quote from provider                                    │
│  2. Normalize to Pydantic model                                │
│  3. Validate quality                                           │
│  4. Record any errors                                          │
│                                                                  │
│  Aggregate into:                                                │
│  MarketSnapshot {                                              │
│    timestamp: 2023-09-06 10:30:15 IST,                        │
│    quotes: {                                                   │
│      "NIFTY": Quote(...),                                      │
│      "BANKNIFTY": Quote(...),                                  │
│      "FINNIFTY": Quote(...)                                    │
│    },                                                           │
│    option_chains: {                                            │
│      "NIFTY": OptionChainSnapshot([...]),                      │
│      ...                                                        │
│    },                                                           │
│    breadth: BreadthSnapshot(...),                              │
│    vix: VIXSnapshot(...),                                      │
│    flows: FlowsSnapshot(...),                                  │
│    meta: {                                                      │
│      "provider": "indstocks",                                  │
│      "quality": {                                              │
│        "NIFTY": DataQualityReport(...),                        │
│        ...                                                      │
│      },                                                         │
│      "errors": []                                              │
│    }                                                            │
│  }                                                              │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│     STORAGE LAYER (app/storage/)                                │
│                                                                  │
│  Development:                                                   │
│  ▪ MemoryStore: Keep snapshots in RAM (fast, for testing)     │
│                                                                  │
│  Production:                                                    │
│  ▪ FirestoreStore: Save to Google Cloud Firestore              │
│    Collections:                                                │
│    └─ market_snapshots/{timestamp}/{symbol}                   │
│       └─ price, bid/ask, OI, Greeks, etc.                     │
│    └─ market_alerts/{timestamp}                               │
│       └─ signal generated (entry, stop, target, etc.)        │
│    └─ paper_trades/{trade_id}                                 │
│       └─ entry, exit, P&L, timestamp, etc.                    │
│    └─ system_events/{timestamp}                               │
│       └─ app start/stop, errors, milestones                  │
│                                                                  │
│  Result: Data persists for backtesting & analysis              │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│     ANALYSIS PIPELINE                                           │
│     (Processes the snapshot to generate insights)              │
│                                                                  │
│  Technical Analysis:                                            │
│  └─ Indicators: SMA, EMA, RSI, MACD, ATR, Supertrend, etc.    │
│                                                                  │
│  Options Analysis:                                              │
│  └─ Greeks: Delta, Gamma, Theta, Vega                         │
│  └─ IV: Implied Volatility                                    │
│  └─ PCR: Put/Call Ratio                                       │
│  └─ OI: Open Interest analysis                                │
│                                                                  │
│  Regime Classification:                                         │
│  └─ Trend: Uptrend, Downtrend, Range, Uncertain             │
│  └─ Volatility: High, Low, Event Risk                        │
│                                                                  │
│  ▼▼▼ All combined into Analysis objects ▼▼▼                   │
│                                                                  │
│  TechnicalIndicators {                                          │
│    close, sma_20, ema_10, rsi_14, macd,                      │
│    atr_14, supertrend, structure, volume, etc.               │
│  }                                                              │
│                                                                  │
│  OptionMetrics {                                               │
│    call_oi, put_oi, pcr, iv, atm_calls, atm_puts,           │
│    delta, gamma, theta, vega, etc.                           │
│  }                                                              │
│                                                                  │
│  RegimeAssessment {                                            │
│    regime, trend, volatility, event_risk,                     │
│    adx, breadth_score, vix, etc.                             │
│  }                                                              │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│     STRATEGY EVALUATION                                         │
│     (7 strategies evaluate the snapshot)                        │
│                                                                  │
│  For EACH strategy:                                             │
│  1. Check if applicable (regime matches)                       │
│  2. Check has_setup() (condition present)                      │
│  3. If yes, calculate entry/stop/targets                       │
│  4. Calculate expected value & factors                         │
│  5. Generate StrategyCandidate                                 │
│                                                                  │
│  Result: 0-7 candidates generated                              │
│  (Usually 2-3 candidates per cycle)                            │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│     SIGNAL SCORING & RISK CHECK                                 │
│     (Rank candidates by quality & check risk)                   │
│                                                                  │
│  For EACH candidate:                                            │
│  1. Verify data quality is VALID                               │
│  2. Calculate factor score                                     │
│  3. Check risk limits (position size, account risk)            │
│  4. Apply transaction costs to EV                              │
│  5. Assign rating: NO_TRADE → STRONG_BUY                      │
│                                                                  │
│  Scoring:                                                       │
│  factor_score = avg(trend, volume, momentum, etc.)            │
│  rating:                                                        │
│    0.0 - 0.25: NO_TRADE (avoid)                               │
│    0.25 - 0.50: CAUTION (risky)                               │
│    0.50 - 0.70: BUY (decent)                                  │
│    0.70 - 0.85: STRONG_BUY (good)                             │
│    0.85 - 1.0: EXCEPTIONAL (excellent)                        │
│                                                                  │
│  Result: Ranked list of recommendations                        │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│     NOTIFICATION & PAPER TRADING                                │
│                                                                  │
│  Telegram Alert:                                                │
│  (Trader sees this on their phone)                              │
│  ┌──────────────────────────────────────────────┐             │
│  │ 🎯 STRONG_BUY Signals (10:30 AM)             │             │
│  │                                              │             │
│  │ 1️⃣ VWAP Momentum                            │             │
│  │    Entry: 25,432 | SL: 25,287 | TGT: 25,692 │             │
│  │    Score: 0.77 | Risk: ₹145                 │             │
│  │                                              │             │
│  │ 2️⃣ Trend Continuation                       │             │
│  │    Entry: 25,432 | SL: 25,287 | TGT: 25,722 │             │
│  │    Score: 0.75 | Risk: ₹145                 │             │
│  │                                              │             │
│  │ 📊 Market: STRONG_UPTREND | VIX: 14.2      │             │
│  └──────────────────────────────────────────────┘             │
│                                                                  │
│  Paper Trading (Simulated):                                     │
│  ▪ Track trader's manual decision (accept/reject)              │
│  ▪ If accepted, record entry as simulated trade               │
│  ▪ Monitor stop-loss & targets in real-time                   │
│  ▪ Record exit price & P&L when target/SL hit                │
│  ▪ Update paper trader performance metrics                    │
│                                                                  │
│  Outcome: Trade logs stored in Firestore                       │
│  └─ paper_trades/{trade_id}: entry, exit, P&L, date/time    │
└─────────────────────────┬──────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│     LOGGING & AUDIT TRAIL                                       │
│                                                                  │
│  All decisions logged with context:                             │
│                                                                  │
│  market.data       - Data collection logs                       │
│  market.analysis   - Technical/options/regime analysis          │
│  market.strategy   - Strategies evaluated & signals             │
│  market.scoring    - Rating & risk checks                       │
│  market.trading    - Paper trade entries/exits                  │
│  market.telegram   - Alerts sent                                │
│  market.error      - Any failures (API errors, etc.)           │
│                                                                  │
│  Stored in:                                                     │
│  - Console (real-time)                                          │
│  - Firestore (persisted)                                        │
│  - Log files (debugging)                                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Real Data Collection: Step-by-Step

### **Scenario: It's 10:30 AM IST, Market is Open**

#### **Step 1: Trigger Data Collection**
```python
# app/orchestration/runner.py
context.provider.collect_and_persist(context)
# OR scheduled by app/orchestration/scheduler.py during market hours
```

#### **Step 2: INDstocks Provider Fetches Data**

**Request:**
```http
GET https://api.indstocks.com/quotes?symbols=NIFTY,BANKNIFTY,FINNIFTY
Authorization: Bearer YOUR_24_HOUR_TOKEN
```

**Response (raw JSON):**
```json
{
  "status": 200,
  "data": [
    {
      "symbol": "NIFTY",
      "name": "NIFTY 50",
      "ltp": "25432.45",
      "bid": "25431.00",
      "ask": "25433.00",
      "open": "25300.00",
      "high": "25500.00",
      "low": "25280.00",
      "close": "25432.45",
      "volume": "120000",
      "timestamp": "1694001000000",
      "oi": "450000"
    },
    ...
  ]
}
```

#### **Step 3: Fetch Option Chains**

**Request:**
```http
GET https://api.indstocks.com/option-chain?symbol=NIFTY&expiry=2023-09-28
```

**Response (raw JSON):**
```json
{
  "status": 200,
  "underlying": {
    "spot": 25432.45,
    "timestamp": 1694001000000
  },
  "options": [
    {
      "strike": 25000,
      "expiry": "2023-09-28",
      "call": {
        "oi": 125000,
        "ltp": 650.00,
        "bid": 648.00,
        "ask": 652.00,
        "volume": 5000,
        "iv": 15.2,
        "delta": 0.85,
        "gamma": 0.002,
        "theta": -0.45,
        "vega": 0.12,
        "change_in_oi": 2000
      },
      "put": {
        "oi": 85000,
        "ltp": 180.00,
        "bid": 178.00,
        "ask": 182.00,
        "volume": 3000,
        "iv": 15.5,
        "delta": -0.15,
        "gamma": 0.002,
        "theta": 0.25,
        "vega": 0.10,
        "change_in_oi": -1000
      }
    },
    ... (50+ more strikes)
  ]
}
```

#### **Step 4: Normalize Raw Data**

**Before (raw JSON):**
```python
{
  "symbol": "NIFTY",
  "ltp": "25432.45",  # String!
  "timestamp": "1694001000000"  # Milliseconds!
}
```

**After (Pydantic model):**
```python
Quote(
  symbol="NIFTY",
  ltp=25432.45,  # Float ✓
  bid=25431.00,
  ask=25433.00,
  timestamp=datetime(2023, 9, 6, 10, 30, 0, tzinfo=IST),  # IST datetime ✓
  source="indstocks"
)

OptionChainEntry(
  strike=25000.0,
  option_type=OptionType.CALL,
  expiry_date=datetime(2023, 9, 28, 15, 30, 0, tzinfo=IST),
  open_interest=125000,
  change_in_oi=2000,
  last_price=650.0,
  bid=648.0,
  ask=652.0,
  iv=0.152,  # 15.2% as decimal
  delta=0.85,
  gamma=0.002,
  theta=-0.45,
  vega=0.12
)
```

#### **Step 5: Validate Data Quality**

**Checks:**
```python
# Check prices are reasonable
assert ltp > 0, "Price must be positive"
assert bid < ask, "Bid must be less than ask"
assert bid <= ltp <= ask, "LTP must be between bid/ask"

# Check timestamp is fresh
age_seconds = (now - timestamp).total_seconds()
assert age_seconds < 120, "Data must be < 2 min old"

# Check OI changes are reasonable
change_pct = abs(change_in_oi) / open_interest * 100
assert change_pct < 50, "OI change can't be > 50%"

# Check Greeks are valid
assert -1 <= delta <= 1, "Delta must be [-1, 1]"
assert gamma > 0, "Gamma must be positive"
```

**Quality Report:**
```python
DataQualityReport(
  status=DataQualityStatus.VALID,
  warnings=[],
  age_seconds=12,
  message="Quote is fresh and valid"
)
```

#### **Step 6: Fetch Breadth (from NSE provider)**

**Request:**
```http
GET https://www.nseindia.com/api/chart-data?index=nifty_50
```

**Response parsing:**
```python
# Parse HTML table from NSE website
BreadthSnapshot(
  timestamp=datetime(2023, 9, 6, 10, 30, 0, tzinfo=IST),
  stocks_up=1600,
  stocks_down=800,
  unchanged=50,
  breadth_index=800 / 1600,  # 0.5
  breadth_strength="BULLISH"  # More up than down
)
```

#### **Step 7: Fetch VIX (from NSE provider)**

**Request:**
```http
GET https://www.nseindia.com/api/live-vix
```

**Response:**
```python
VIXSnapshot(
  timestamp=datetime(2023, 9, 6, 10, 30, 0, tzinfo=IST),
  value=14.2,
  change=-0.5,
  change_pct=-3.4,
  interpretation="LOW_VOLATILITY"  # VIX < 15
)
```

#### **Step 8: Aggregate into MarketSnapshot**

**Result:**
```python
snapshot = MarketSnapshot(
  timestamp=datetime(2023, 9, 6, 10, 30, 0, tzinfo=IST),
  
  # All quotes (indexed by symbol)
  quotes={
    "NIFTY": Quote(...),
    "BANKNIFTY": Quote(...),
    "FINNIFTY": Quote(...)
  },
  
  # All option chains
  option_chains={
    "NIFTY": OptionChainSnapshot(
      underlying_symbol="NIFTY",
      spot_price=25432.45,
      expiry_date=datetime(2023, 9, 28, 15, 30, 0, tzinfo=IST),
      entries=[
        OptionChainEntry(strike=25000, option_type=CALL, ...),
        OptionChainEntry(strike=25000, option_type=PUT, ...),
        ... (50+ more entries)
      ]
    ),
    "BANKNIFTY": OptionChainSnapshot(...),
    "FINNIFTY": OptionChainSnapshot(...)
  },
  
  # Breadth & volatility
  breadth=BreadthSnapshot(...),
  vix=VIXSnapshot(...),
  flows=FlowsSnapshot(...),
  
  # Metadata
  meta={
    "provider": "indstocks",
    "quality": {
      "NIFTY": DataQualityReport(status=VALID),
      "BANKNIFTY": DataQualityReport(status=VALID),
      "FINNIFTY": DataQualityReport(status=VALID),
      "breadth": DataQualityReport(status=VALID),
      "vix": DataQualityReport(status=VALID)
    },
    "errors": []  # Empty if all succeeded
  }
)
```

#### **Step 9: Persist Snapshot**

**Development (MemoryStore):**
```python
store.save_market_snapshot(snapshot)
# Saved in RAM, cleared on app restart
```

**Production (FirestoreStore):**
```python
store.save_market_snapshot(snapshot)
# Saves to:
# firestore:
#   └─ market_snapshots/
#      └─ 2023-09-06T10:30:00/
#         ├─ NIFTY: {ltp: 25432.45, bid: 25431, ask: 25433, ...}
#         ├─ BANKNIFTY: {...}
#         ├─ FINNIFTY: {...}
#         ├─ breadth: {up: 1600, down: 800, ...}
#         └─ vix: {value: 14.2, ...}
```

---

## WebSocket Real-Time Price Updates

While the REST API fetches on a schedule (e.g., every 5 seconds), the INDstocks WebSocket keeps prices fresh in between.

```python
# Background thread (started at app startup)
ws_feed = _INDstocksWebSocketFeed(
  access_token="YOUR_TOKEN",
  ws_instruments={"NIFTY": "NIDX:some_token", ...},
  cache=_QuoteStreamCache()
)
ws_feed.start()  # Runs in background thread

# Connection loop:
while not stop:
  connect to wss://ws-prices.indstocks.com
  subscribe to ["NIDX:token1", "NIDX:token2", ...]
  
  while connected:
    msg = ws.recv()  # {"mode": "ltp", "instrument": "NIDX:token", "data": {"ltp": 25432.45}}
    cache.update("NIFTY", ltp=25432.45, ts_ms=now_ms)
    
  # Disconnected (error/timeout)
  wait exponential backoff (3s → 60s)
  reconnect

# When REST API fetches a quote:
ltp = cache.get("NIFTY", max_age_seconds=30)
# If cache age < 30s and has data, use it (fresh!)
# Otherwise, fall back to REST API
```

---

## Error Handling & Graceful Degradation

```
Provider Error Scenario:
┌──────────────────────────────────────────────┐
│ 🔴 INDstocks API returns HTTP 500 (internal) │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ MarketDataCollector catches ProviderError    │
│ self._record_error(snapshot, "NIFTY",        │
│   "quote: HTTP 500 Internal Server Error")   │
└──────────────────────┬───────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────┐
│ Snapshot quality marked as WARNING           │
│                                              │
│ snapshot.meta["quality"]["NIFTY"] =          │
│   DataQualityReport(                         │
│     status=WARNING,                          │
│     errors=["HTTP 500 from INDstocks"],      │
│     message="Data unavailable, skipping"     │
│   )                                          │
│                                              │
│ ✓ App doesn't crash                          │
│ ✓ Other symbols still process                │
│ ✓ Telegram alerted to data issue             │
│ ✓ Strategy won't generate signals for NIFTY  │
│   (invalid data gate)                        │
└──────────────────────────────────────────────┘
```

---

## Data Flow Checklist

- [x] Real data: YES, fetched from live APIs (not simulated)
- [x] Error handling: YES, graceful degradation with quality reports
- [x] Caching: YES, WebSocket + REST fallback
- [x] Timestamps: YES, IST-aware, validated freshness
- [x] Validation: YES, checks prices, OI, Greeks for anomalies
- [x] Persistence: YES, stored in Firestore for backtesting
- [x] Audit trail: YES, all errors logged
- [x] Reproducible: YES, stored snapshots can be replayed

---

## For Developers: Adding a New Data Source

To add a new provider (e.g., Zerodha Kite API):

```python
# 1. Create new provider class
# app/data/providers/zerodha.py

from app.data.providers.base import MarketDataProvider, ProviderError, RawPayload

class ZerodhaMarketDataProvider(MarketDataProvider):
    """Zerodha Kite API provider."""
    
    name = "zerodha"
    
    def __init__(self, api_key: str, access_token: str):
        self.api_key = api_key
        self.access_token = access_token
        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)
    
    def get_quote(self, symbol: str) -> RawPayload:
        """Fetch quote from Zerodha Kite."""
        try:
            # Kite API returns dict
            data = self.kite.quote(f"NSE:{symbol}")
            return data
        except Exception as exc:
            raise ProviderError(f"Zerodha quote error: {exc}")
    
    def get_option_chain(self, symbol: str) -> RawPayload:
        # Similar implementation
        pass
    
    # ... etc

# 2. Register in factory
# app/data/providers/factory.py

def create_provider(config: ProviderConfig) -> MarketDataProvider:
    if config.provider_type == "indstocks":
        return INDstocksMarketDataProvider(...)
    elif config.provider_type == "zerodha":
        return ZerodhaMarketDataProvider(...)
    else:
        raise ProviderError(f"Unknown provider: {config.provider_type}")

# 3. Update config
# config/default.yaml

provider:
  provider_type: zerodha  # or "indstocks"
  zerodha:
    api_key: ${ZERODHA_API_KEY}
    access_token: ${ZERODHA_ACCESS_TOKEN}

# 4. Update normalizer (if Zerodha format differs)
# app/data/normalizers/__init__.py

def normalize_quote(self, raw: RawPayload, symbol: str) -> Quote:
    if self.provider_type == "zerodha":
        # Zerodha returns {"NSE:NIFTY": {...}}
        data = raw.get(f"NSE:{symbol}", {})
    else:  # indstocks
        data = raw
    
    return Quote(
        symbol=symbol,
        ltp=float(data["last_price"]),
        ...
    )
```

---

Good luck implementing! 🚀
