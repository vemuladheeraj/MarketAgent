# MarketAgent - Production Dashboard Implementation ✅

## 🎯 Executive Summary

MarketAgent is a **complete, working trading decision-support system** that:
- ✅ Runs 24/5 across Indian (9:15-3:30 IST) + US (9:30-4:00 EST) markets
- ✅ Generates AI-powered trade recommendations via Gemini
- ✅ Provides a web dashboard for visual signal monitoring
- ✅ Enforces **manual order placement only** (no auto-execution)
- ✅ Tracks paper trading performance
- ✅ Produces actionable trade briefs with step-by-step broker instructions

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│         MarketAgent Pipeline Daemon                      │
│  (Market Data → Technical → Options → Regime → Signals)  │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴──────────────┐
         │                          │
    ┌────▼────┐           ┌────────▼────────┐
    │ Gemini  │           │  Trade Advisor  │
    │   AI    │           │  (Brief Builder)│
    └────┬────┘           └────────┬────────┘
         │                         │
    ┌────▼─────────────────────────▼────┐
    │      MarketStore (Firestore)       │
    │  (Signals, Briefs, Paper Trades)   │
    └────────────────────┬───────────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
    ┌────▼──────────────┐    ┌──────────▼─────────┐
    │  FastAPI Backend  │    │  React Dashboard   │
    │  (REST Endpoints) │    │  (Web UI)          │
    └────┬──────────────┘    └──────────┬─────────┘
         │                              │
         └──────────────┬───────────────┘
                        │
                   User's Browser
                   (Signals + Manual Orders)
```

---

## 🚀 What You Can Do Now

### 1. Start the Backend

```bash
python -m app.web.server --web-port 8000
```

**What starts:**
- Market data collection daemon (runs pipeline cycles every 5-30 seconds)
- Gemini AI advisor for market reasoning
- Paper trading engine tracking positions
- REST API on `http://localhost:8000`

**Check health:**
```bash
curl http://localhost:8000/api/health
```

### 2. Get Recent Trading Signals

```bash
curl http://localhost:8000/api/signals | jq '.[0]'
```

Example response:
```json
{
  "symbol": "NIFTY",
  "strategy": "opening_range_breakout",
  "direction": "long",
  "entry": 24750.5,
  "stop_loss": 24650.0,
  "targets": [24900.0, 25050.0],
  "score": 82,
  "accepted": true,
  "timestamp": "2026-09-01T14:30:00+05:30"
}
```

### 3. Get Actionable Trade Brief

```bash
curl http://localhost:8000/api/brief/NIFTY | jq '.'
```

Example response:
```json
{
  "symbol": "NIFTY",
  "action": "BUY",
  "strategy": "vwap_momentum",
  "entry": 245.50,
  "stop_loss": 235.00,
  "targets": [260.0, 275.0],
  "contract": {
    "tradingsymbol": "NIFTY 24750 CE",
    "bid": 245.25,
    "ask": 245.75,
    "delta": 0.65,
    "open_interest": 15000
  },
  "rationale": [
    "Strategy: VWAP momentum breakout on 1D chart",
    "Regime: Strong uptrend with 92% confidence"
  ],
  "warnings": [
    "Contract expires in 4 days - theta decay accelerating"
  ]
}
```

### 4. Ask Gemini AI Questions

```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the market regime today?"}'
```

Example response:
```json
{
  "question": "What is the market regime today?",
  "answer": "The market is in a strong uptrend based on RSI > 70, consecutive higher highs, and VWAP above the 20-EMA. Volatility (VIX) is elevated at 18. Watch for mean-reversion pullbacks to the 20-day moving average as potential entries."
}
```

### 5. View Paper Trading Positions

```bash
curl http://localhost:8000/api/paper-trades | jq '.'
```

### 6. Run Web Dashboard

In another terminal:
```bash
cd web
npm install
npm run dev
```

Then open: **http://localhost:3000**

---

## 📊 Web Dashboard Features

### Trade Brief Card
Shows **what you should do right now** with:
- ✅ Entry price (exact premium level)
- ✅ Stop loss price (downside protection)
- ✅ Target prices (profit levels)
- ✅ Step-by-step broker instructions for manual order placement
- ✅ Risk/reward ratios
- ✅ Position sizing guidance
- ✅ Warnings about market conditions

### Recent Signals Table
All strategy-generated trading candidates with confidence scores

### Paper Trades
Track open and closed positions with P&L

### Symbol Selector
Quick access to NIFTY, BANKNIFTY, US tickers (NVDA, TSLA, SPY, etc.)

---

## 🔧 Key Components Implemented

### Backend (Python)

| Component | Purpose | Status |
|-----------|---------|--------|
| `app.web.api` | REST endpoints for signals, briefs, market data | ✅ Complete |
| `app.web.server` | FastAPI server + daemon threading | ✅ Complete |
| `app.data.normalizers.us_options` | Yahoo Finance option-chain processing | ✅ Complete |
| `app.data.providers.us_markets` | yfinance integration (optional import) | ✅ Complete |
| `app.orchestration.pipeline` | Full signal generation pipeline | ✅ Pre-existing |
| `app.advisor.advisor` | Trade brief generation logic | ✅ Pre-existing |
| `app.ai.enhanced_advisor` | Gemini-powered insights | ✅ Pre-existing |

### Frontend (React/TypeScript)

| Component | Purpose | Status |
|-----------|---------|--------|
| `apiService.ts` | REST client library | ✅ Complete |
| `useApi.ts` | React hooks for polling | ✅ Complete |
| `Dashboard.tsx` | Main layout + tab navigation | ✅ Complete |
| `ApiBriefCard.tsx` | Trade brief with broker steps | ✅ Complete |
| `ApiSignalsTable.tsx` | Signals table display | ✅ Complete |

---

## 💻 System Requirements

### Minimum
- Python 3.12+
- Node.js 18+ (for web dashboard)
- 512 MB RAM

### Recommended
- Python 3.13
- 2GB RAM
- Stable internet connection

### Dependencies
```
Core: pydantic, pyyaml, firebase-admin, google-genai, pandas, numpy
Web: fastapi, uvicorn
Optional: yfinance (for US markets)
Frontend: React, TypeScript, Tailwind CSS
```

---

## 🎯 Trading Workflow

### Step 1: Check Dashboard
Visit **http://localhost:3000** (web) or **curl /api/brief/NIFTY** (API)

### Step 2: Review Trade Brief
The system shows:
- What to do (BUY/SELL/WAIT)
- Exact entry price for your order
- Where to put your stop loss
- Where to take profits
- Risk vs. reward ratio

### Step 3: Manual Order Placement
Open your broker (Zerodha, DHAN, etc.) and:
1. Search for the option contract shown (e.g., "NIFTY 24750 CE")
2. Place a BUY order at the entry price
3. Set stop-loss order at the price shown
4. Set take-profit order at the target price

### Step 4: Monitor
Dashboard updates every 5 seconds with live P&L and current prices

### Step 5: Exit
When your order hits stop or target, you exit manually

---

## 🔐 Safety Features

✅ **No Auto-Execution**: System never places orders (you do it manually)  
✅ **Paper Trading**: Track performance before risking real money  
✅ **Manual Control**: All exits are human-decided  
✅ **Risk Limits**: Position sizing respects account size  
✅ **Data Quality Gates**: Signals rejected if data is invalid  

---

## 📈 Performance Tracking

The dashboard shows:
- **Entry Price**: What you paid
- **Current P&L**: Unrealized profit/loss in ₹
- **P&L %**: Return as a percentage
- **Strategy Used**: Which strategy generated this trade
- **Entry Targets**: Your planned exit prices

---

## 🎓 Configuration

Create `config/my_settings.yaml`:

```yaml
market:
  active_markets:
    - "in"      # India (9:15-3:30 IST)
    - "us"      # US (9:30-4:00 EST)

provider:
  name: "us_markets"  # or "nse", "indstocks"

gemini:
  api_key: "${GEMINI_API_KEY}"  # Set env var

strategies:
  enabled_strategies:
    - "vwap_momentum"
    - "us_small_cap_momentum_breakout"
    - "opening_range_breakout"

advisor:
  enabled: true
  min_score: 70.0
  enable_web_dashboard: true
  web_port: 8000
```

Then run:
```bash
python -m app.web.server --config config/my_settings.yaml
```

---

## 📚 API Reference

### Health
`GET /api/health` → `{"status": "ok"}`

### Signals
`GET /api/signals` → List of recent trading signals

### Brief
`GET /api/brief/{symbol}` → Current trade recommendation

### Market
`GET /api/market/{symbol}` → Live quote with bid/ask

### Regime
`GET /api/regime/{symbol}` → Market condition classification

### Ask AI
`POST /api/ask` → Answer trader questions via Gemini

### Trades
`GET /api/paper-trades` → All paper trading positions

---

## 🐛 Troubleshooting

### "No signals available"
✅ Check market hours (9:15-3:30 IST for India, 9:30-4:00 EST for US)  
✅ Verify config has symbols you want to trade  
✅ Check logs: `tail -f logs/app.log`

### "Gemini API error"
✅ Verify `GEMINI_API_KEY` environment variable is set  
✅ Check your Google Cloud project has Gemini enabled  
✅ System degrades gracefully without Gemini

### "Dashboard won't load"
✅ Ensure backend is running: `curl http://localhost:8000/api/health`  
✅ Check CORS settings in vite config  
✅ Run `cd web && npm install` if first time

### "yfinance not found"
✅ `pip install yfinance>=0.2.32`  
✅ System still works for Indian market without it

---

## 🚀 Next Steps

1. **Configure for your symbols**
   - Edit `config/default.yaml` with your watchlist

2. **Add Gemini API key** (optional but recommended)
   - Get key from https://ai.google.dev
   - Set `GEMINI_API_KEY` environment variable

3. **Run the backend**
   - `python -m app.web.server`

4. **Build the web dashboard**
   - `cd web && npm run build`

5. **Start trading**
   - Review signals on dashboard
   - Place orders manually at recommended prices
   - Track P&L automatically

---

## 📞 Support

**Common Issues:**
- Check [DASHBOARD_README.md](DASHBOARD_README.md) for detailed docs
- Run `python -m app.main --print-config` to verify config
- Check API: `curl http://localhost:8000/api/health`

**Development:**
- Logs: `logs/app.log`
- Tests: `pytest tests/`
- Code style: No linting required, just works

---

## ✨ Key Achievements

✅ Complete REST API with 7 endpoints  
✅ React web dashboard with real-time updates  
✅ Trade brief generation with broker instructions  
✅ 24/5 multi-market scheduling  
✅ Optional Gemini AI integration  
✅ Paper trading with P&L tracking  
✅ Graceful degradation (works without optional dependencies)  
✅ Timezone-safe datetime handling  
✅ Production-ready error handling  

---

**MarketAgent is ready for production use.** Start the backend, open the dashboard, and begin making informed trading decisions with AI-powered recommendations and manual control. 🎯
