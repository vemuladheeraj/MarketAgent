# MarketAgent Dashboard - Getting Started Guide

## 🎯 What is MarketAgent?

MarketAgent is a **production-ready trading decision-support system** for:
- **Indian Markets (NSE)**: NIFTY, BANKNIFTY, and equity options (9:15-3:30 IST)
- **US Markets**: Stock options & small-cap momentum intraday trading (9:30-4:00 EST)

**Key Features:**
- ✅ **No Auto-Execution**: All trades are manually placed by you
- ✅ **AI-Powered Insights**: Gemini AI explains every trade idea
- ✅ **24/5 Operation**: Covers both Indian (India time) + US (NY time) markets
- ✅ **Real-time Decision Support**: Web dashboard with live signals and recommendations
- ✅ **Paper Trading**: Track performance without real money at risk

---

## 🚀 Quick Start

### Prerequisites

```bash
# Check you have Python 3.12+
python --version

# Activate the virtual environment
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # macOS/Linux
```

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Configure the System

Copy the example config and edit it:

```bash
cp config/default.yaml config/my_settings.yaml
```

Edit `config/my_settings.yaml`:

```yaml
# Market Configuration
market:
  timezone: Asia/Kolkata
  active_markets:  # [] = Indian market only, ["us"] = US only, ["in", "us"] = both
    - "in"
    - "us"

# Data Provider
provider:
  name: "us_markets"  # "nse" for Indian only, "us_markets" for US, "indstocks" for combo

# Gemini AI (optional but recommended)
gemini:
  api_key: "${GEMINI_API_KEY}"  # Set env var or paste your API key

# Web Dashboard
web:
  enable_web_dashboard: true
  web_port: 8000
```

### Step 3: Run the Dashboard Backend

```bash
python -m app.web.server --config config/my_settings.yaml --web-port 8000
```

The API will start on `http://localhost:8000`

**Endpoints available:**
- `GET /api/health` - Health check
- `GET /api/signals` - Recent trading signals
- `GET /api/brief/{symbol}` - Trade recommendation for a symbol
- `GET /api/market/{symbol}` - Current market quote
- `GET /api/paper-trades` - All paper trading positions
- `GET /api/regime/{symbol}` - Market regime classification
- `POST /api/ask` - Ask Gemini AI a question

### Step 4: Run the Web Dashboard (Optional)

In a new terminal:

```bash
cd web
npm install
npm run dev
```

The dashboard will open at `http://localhost:3000`

### Step 5: View Live Signals

Once the backend is running, you can:
1. Check signals at: `curl http://localhost:8000/api/signals`
2. Get a trade brief for NIFTY: `curl http://localhost:8000/api/brief/NIFTY`
3. Ask the AI: `curl -X POST http://localhost:8000/api/ask -H "Content-Type: application/json" -d '{"question":"What is the market regime?"}'`

---

## 📊 Dashboard Components

### Trade Brief Card
Shows **actionable recommendations** with:
- Entry, Stop Loss, Target prices
- Step-by-step broker instructions for manual order placement
- Risk/reward ratios and position sizing
- Warnings about market conditions

### Recent Signals Table
Displays all strategy-generated trading setup candidates with:
- Symbol, Strategy, Direction
- Entry/Stop/Target levels
- Confidence score
- Acceptance status

### Paper Trading Positions
Track open/closed positions:
- Entry price and time
- Current unrealized P&L
- Strategy used
- Entry targets and stops

### Market Data
Live quotes, bid/ask spreads, and volume for each symbol

---

## 🎓 Understanding Trade Briefs

A **Trade Brief** is the system's answer to: **"What should I do right now?"**

**Action Types:**

1. **BUY** - Buy this option contract now
   - Exact entry price and broker steps included
   - Stop loss and target prices provided
   - Risk sizing guidance

2. **SELL** - (Coming: sell-side option strategies)
   - Income strategies like covered calls, cash-secured puts

3. **WAIT** - Stand aside
   - Reason explained (data quality, regime mismatch, no setups)
   - Auto-expires when recommendation window closes

---

## 💡 Trading Workflow

### 1. Check the Dashboard
Visit `http://localhost:3000` (if running web dev server) or use the API directly

### 2. Review the Trade Brief
Read the **Trade Brief** for your target symbol:
- Understand the strategy
- Check entry/stop/target levels
- Review broker instructions
- Note any warnings

### 3. Verify Live Prices
Check your broker platform for current prices

### 4. Place Order Manually
Follow the step-by-step instructions in the brief to:
- Buy the recommended option contract
- Set stop-loss order
- Set target order

### 5. Monitor Position
Track P&L in the **Paper Trades** section (actual tracking starts after you place the trade)

### 6. Exit at Target or Stop
The system doesn't exit automatically — you control all exits

---

## 🔧 Configuration Reference

### Active Markets
```yaml
market:
  active_markets:
    - "in"      # Indian market (9:15-3:30 IST)
    - "us"      # US market (9:30-4:00 EST)
```

### Data Providers
```yaml
provider:
  name: "us_markets"  # Options: "nse", "us_markets", "indstocks"
  params:
    tickers:         # Symbols to monitor
      - "NVDA"
      - "TSLA"
      - "SPY"
```

### Strategy Configuration
```yaml
strategies:
  enabled_strategies:
    - "opening_range_breakout"
    - "vwap_momentum"
    - "us_small_cap_momentum_breakout"  # US intraday
    - "mean_reversion"                  # Indian
```

### Advisor Settings
```yaml
advisor:
  enabled: true
  min_score: 70.0              # Only show briefs above 70% confidence
  validity_minutes: 10         # Brief auto-expires after 10 min
  enable_web_dashboard: true
  web_port: 8000
```

---

## 🧪 Testing Without Real Data

To test with stub data:

```bash
export DATA_PROVIDER=nse
python -m app.main --print-config
```

This will print your config without running the pipeline.

---

## 📚 API Reference

### Health Check
```bash
curl http://localhost:8000/api/health
```

**Response:**
```json
{
  "status": "ok",
  "service": "MarketAgent"
}
```

### Get Recent Signals
```bash
curl http://localhost:8000/api/signals
```

**Response:**
```json
[
  {
    "symbol": "NVDA",
    "strategy": "vwap_momentum",
    "direction": "long",
    "entry": 123.45,
    "stop_loss": 120.0,
    "targets": [130.0, 135.0],
    "score": 85,
    "classification": "high_quality",
    "accepted": true,
    "timestamp": "2026-09-01T14:30:00+05:30"
  }
]
```

### Get Trade Brief for a Symbol
```bash
curl http://localhost:8000/api/brief/NVDA
```

**Response:**
```json
{
  "symbol": "NVDA",
  "action": "BUY",
  "strategy": "vwap_momentum",
  "entry": 6.25,
  "stop_loss": 5.00,
  "targets": [8.50, 10.0],
  "contract": {
    "tradingsymbol": "NVDA 125 CE",
    "strike": 125.0,
    "option_type": "call",
    "bid": 6.15,
    "ask": 6.35,
    "delta": 0.65,
    "open_interest": 1500
  },
  "rationale": [
    "Strategy: VWAP momentum breakout...",
    "Regime: Strong uptrend with 92% confidence..."
  ],
  "warnings": [
    "Premium spread 3.2% is tight — use limit orders"
  ]
}
```

### Ask Gemini AI
```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What is the current market regime?"}'
```

**Response:**
```json
{
  "question": "What is the current market regime?",
  "answer": "The market is in a strong uptrend with high conviction based on RSI > 70 and consecutive higher highs. Volatility is elevated (VIX 18) suggesting momentum continuation. Watch for mean-reversion pullbacks to the 20-EMA."
}
```

---

## ⚙️ Advanced Configuration

### Environment Variables

```bash
export GEMINI_API_KEY="your-key-here"
export APP_CONFIG_PATH="config/my_settings.yaml"
export DATA_PROVIDER="us_markets"
export FIREBASE_PROJECT_ID="your-firestore-project"
```

### Running Multiple Instances

To monitor different symbols:

```bash
# Terminal 1: US market focus
python -m app.web.server --config config/us_settings.yaml --web-port 8000

# Terminal 2: Indian market focus
python -m app.web.server --config config/india_settings.yaml --web-port 8001
```

---

## 🐛 Troubleshooting

### "yfinance is not installed"
```bash
pip install yfinance>=0.2.32
```

### "API connection failed"
Make sure the backend is running:
```bash
curl http://localhost:8000/api/health
```

### "No signals available"
Check that:
1. Market hours are active
2. Symbols are configured correctly
3. Strategy is enabled in config
4. Data provider is accessible

### "Dashboard won't load"
1. Ensure backend is running on port 8000
2. Run `cd web && npm run build` if serving static build
3. Check browser console for CORS errors

---

## 📖 Understanding the Output

### Signal Classification
- **NO_TRADE** (0-30): Not a trade candidate
- **WEAK** (30-50): Weak setup, risky
- **WATCH** (50-70): Monitor but don't trade yet
- **VALID** (70-85): Good setup, follow the brief
- **HIGH_QUALITY** (85-95): Excellent setup
- **EXCEPTIONAL** (95-100): Rare high-conviction setup

### Regime
- **STRONG_UPTREND**: Buy calls, sell puts
- **UPTREND**: Cautious buys on dips
- **RANGE**: Sell premium at resistance, buy at support
- **DOWNTREND**: Cautious shorts, avoid longs
- **STRONG_DOWNTREND**: Buy puts, sell calls
- **HIGH_VOLATILITY**: Wider stops, smaller position sizes
- **LOW_VOLATILITY**: Watch for breakouts

---

## 🔐 Security Notes

- **No API Keys in Git**: Use `.env` file or environment variables
- **Local Dashboard Only**: Dashboard runs on `127.0.0.1` by default
- **Manual Execution**: The system never places orders automatically
- **Paper Trading**: Track performance safely without real money

---

## 📞 Support

For issues:
1. Check the logs: `cat logs/app.log`
2. Run diagnostics: `python -m app.main --print-config`
3. Test the API: `curl http://localhost:8000/api/health`

---

## 🎉 Next Steps

1. **Configure your symbols** in `config/my_settings.yaml`
2. **Add your Gemini API key** for AI insights
3. **Run the backend** and check signals
4. **Build the web dashboard** for visual interface
5. **Start trading** with manual order placement

Good luck! 🚀
