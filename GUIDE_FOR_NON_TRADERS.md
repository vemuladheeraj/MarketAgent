# MarketAgent 101: A Guide for Non-Traders

> **For software engineers and data scientists who want to understand this system without trading experience.**

---

## 🎯 Quick Concept Overview

| Concept | Simple Explanation | Real-World Example |
|---------|-------------------|-------------------|
| **Index/Underlying** | A basket of stocks representing the market | NIFTY 50 = top 50 Indian companies |
| **Option Contract** | Right (not obligation) to buy/sell at a fixed price on a date | Buy right to purchase NIFTY at 25000 on Oct 31 |
| **Call** | Bet that price will go UP | "I think NIFTY will rise; I buy a CALL" |
| **Put** | Bet that price will go DOWN | "I think NIFTY will fall; I buy a PUT" |
| **Strike Price** | The fixed price in an option contract | NIFTY 25000CE means buy at 25000 |
| **Premium** | Cost to buy an option (like insurance) | Pay ₹500 for the option contract |
| **Expiry** | Last day the option can be exercised | Oct 31, 2026 (monthly/weekly cycles) |
| **Open Interest (OI)** | How many contracts are currently OPEN | Higher OI = more trader interest |
| **Greeks** | Metrics showing how option price changes with market | Delta, Gamma, Theta, Vega |
| **PCR (Put/Call Ratio)** | Ratio of put contracts vs call contracts | PCR > 1 = more bearish sentiment |
| **Regime** | Current market mood/trend | Uptrend, Downtrend, Range, Volatile |
| **Technical Indicators** | Patterns and formulas for price behavior | Moving averages, RSI, MACD, ATR |

---

## 🏗️ System Architecture (Simplified)

```
┌─────────────────────────────────────────────────────────────┐
│                    MARKET DATA SOURCES                       │
│              (INDstocks + NSE live APIs)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  DATA COLLECTION LAYER                       │
│  ▪ Fetch quotes (current price of NIFTY, BANKNIFTY, etc)   │
│  ▪ Fetch option chains (all strikes & expiries)            │
│  ▪ Fetch market breadth (how many stocks up vs down)       │
│  ▪ Fetch FII/DII flows (foreign/domestic investor money)   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  VALIDATION & NORMALIZATION                  │
│  ▪ Check data quality (mark VALID/WARNING/INVALID)         │
│  ▪ Convert to standard internal format                      │
│  ▪ Record any API errors/failures gracefully                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              QUANTITATIVE ANALYSIS LAYER                     │
│  ▪ Technical Analysis (moving averages, RSI, MACD, etc)    │
│  ▪ Options Analysis (Greeks, IV, PCR, OI analysis)         │
│  ▪ Market Regime Classification (trend vs range, etc)      │
│  ▪ Strategy Scoring (rate quality of trading signals)      │
│  ▪ Risk & Position Sizing (how much to trade)              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              AI LAYER (GEMINI ADVISOR)                       │
│  ▪ Explains what the numbers mean                           │
│  ▪ Interprets latest financial news                         │
│  ▪ Finds contradictions in signals                          │
│  ▪ Answers trader questions in natural language             │
│  🛑 NEVER invents data, bypasses rules, or places trades    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 USER DECISION & ACTION                       │
│  ▪ Trader reads recommendations                             │
│  ▪ Trader manually places trades in their broker app        │
│  ▪ System tracks paper trading (simulated) performance      │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Key Workflows

### **Workflow 1: Getting a Market Snapshot**
```
1. MarketDataCollector.collect_snapshot()
   ├─ For each index (NIFTY, BANKNIFTY):
   │  ├─ Fetch current quote (current price, bid/ask, OI)
   │  ├─ Fetch option chain (all strikes for all expiries)
   │  └─ Validate data quality
   ├─ Fetch market breadth (# stocks up vs down)
   ├─ Fetch VIX (volatility index)
   └─ Fetch FII/DII flows (buyer/seller patterns)

2. All data combined into MarketSnapshot object
3. Saved to storage (Firestore in production)
```
**Real Example:**
```
Time: 10:30 AM IST
NIFTY 50 Quote: 25,432 (↑ 120 points)
  Option Chain for Oct expiry:
    - 25000 CALL: ₹650 premium
    - 25000 PUT: ₹180 premium
    - 25500 CALL: ₹200 premium
  ... (50+ strikes)
Market Breadth: 1,500 stocks up, 900 down
VIX: 14.2 (calm market)
```

### **Workflow 2: Analyzing for Trading Signals**
```
1. TechnicalAnalyzer.compute()
   └─ Calculate: SMA, EMA, RSI, MACD, ATR, Supertrend, etc.

2. OptionsAnalyzer.compute()
   └─ Calculate: Greeks, IV, PCR, OI concentration, etc.

3. RegimeClassifier.classify()
   └─ Answer: "Is it trending up? Down? Ranging? Volatile?"

4. StrategyEngine.score_candidates()
   ├─ Check each strategy's "has_setup" rules
   ├─ Calculate entry, stop-loss, and profit targets
   ├─ Rate each candidate (NO_TRADE, CAUTION, BUY, STRONG_BUY, etc.)
   └─ Filter by regime preference

5. Recommendation created: "BUY NIFTY 25500 CALL @ ₹150, SL ₹100, Target ₹250"
```

---

## 🔧 Code Structure Explained

```
app/
├── main.py
│   └─ Entry point. Loads config, starts the agent.
│      Think: "Application startup script"
│
├── data/
│   ├─ providers/
│   │  ├─ indstocks.py     ← Real live data from INDstocks API
│   │  └─ nse.py           ← NSE data (breadth, VIX, FII/DII)
│   ├─ collectors/
│   │  └─ market_collector.py  ← Orchestrates data fetching
│   ├─ normalizers/        ← Convert API response → internal format
│   └─ validators/         ← Check data quality
│
├── analysis/
│   ├─ technical/          ← SMA, EMA, RSI, MACD, ATR, etc.
│   ├─ options/            ← Greeks, IV, PCR, OI analysis
│   ├─ regime/             ← Market trend classification
│   ├─ breadth/            ← Stock market breadth
│   └─ volatility/         ← Volatility metrics
│
├── scoring/
│   └─ signal_scorer.py    ← Rate trading signals (NO_TRADE → EXCEPTIONAL)
│
├── strategies/
│   ├─ base/strategy.py    ← Abstract strategy template
│   └─ implementations.py  ← Concrete strategies (breakout, VWAP, etc.)
│
├── risk/
│   ├─ engine.py           ← Risk calculations
│   ├─ position_sizing.py  ← How much money to use per trade
│   ├─ costs.py            ← Brokerage, taxes, slippage
│   └─ expected_value.py   ← Win probability × profit/loss
│
├── paper_trading/
│   ├─ engine.py           ← Simulate trades (no real money)
│   └─ tracker.py          ← Record profit/loss on paper trades
│
├── storage/
│   ├─ memory/             ← Dev: Save to RAM
│   └─ firestore/          ← Prod: Save to Google Cloud Firestore
│
├── models/                ← Pydantic data classes (OptionChain, Quote, etc.)
├── ai/gemini/             ← AI advisor (explain numbers & news)
├── notifications/telegram ← Send alerts via Telegram
└── orchestration/
    ├─ pipeline.py         ← Coordinator: "Do data → analysis → signal"
    ├─ runner.py           ← Application lifecycle manager
    └─ scheduler.py        ← Run during market hours only
```

---

## 📈 Specific Use Cases

### **Use Case 1: "When should I buy a CALL?"**

```python
# Data arrives: NIFTY 25432
# System runs:

1. TechnicalAnalyzer
   → Close > SMA_20? YES
   → RSI 14? 68 (overbought)
   → ATR 14? ₹145

2. OptionsAnalyzer (Oct expiry)
   → IV (implied volatility)? 15.2% (low)
   → Call OI? 450,000 contracts
   → Put OI? 320,000 contracts
   → PCR? 0.71 (puts < calls, bullish)

3. RegimeClassifier
   → Trend? STRONG_UPTREND ✓
   → Volatility? LOW ✓

4. StrategyEngine
   Strategy: "OpeningRangeBreakout"
   → Has setup? YES (price > opening high)
   → Direction? LONG (bullish)
   → Entry? 25432
   → Stop Loss? 25200 (opening low)
   → Target? 25662 (entry + 2× risk)
   → Score? 0.82 (STRONG_BUY)

5. Recommendation:
   "BUY 25500 CALL Premium ₹150
    SL: 25200
    Target: 25662"
```

### **Use Case 2: "Is a PUT spread a good idea?"**

The system automatically:
- Checks if we're in a downtrend (regime check)
- Evaluates risk/reward (expected value)
- Sizes the position based on account size
- Tracks it in paper trading
- Alerts you when targets/stops are hit

---

## 🛡️ Risk Management Built In

```
Before ANY recommendation:
1. Account Size Check
   → "Account is ₹500,000"

2. Position Sizing
   → "Risk ₹5,000 max per trade (1% of account)"
   → "If SL is 230 points away, buy only X contracts"

3. Transaction Costs
   → Brokerage fee
   → STT (securities transaction tax)
   → GST on brokerage
   → Slippage (price moved by the time order executes)

4. Expected Value
   → Win Probability: 50% (uninformed prior)
   → Win Amount: ₹5,000
   → Loss Amount: -₹5,000
   → EV = (0.5 × ₹5,000) + (0.5 × -₹5,000) = 0
   → Result: NO_TRADE (risk/reward not good enough)

5. Data Quality Gate
   → If quote is INVALID, don't generate signal
```

---

## 🔴 What MarketAgent Does NOT Do

❌ Place real trades with your money  
❌ Guarantee profits  
❌ Use AI to invent trading ideas  
❌ Bypass risk controls  
❌ Trade during market closure hours  
❌ Predict the future  

---

## 🟢 What MarketAgent DOES Do

✅ Fetch real live market data  
✅ Calculate technical & options metrics  
✅ Score trading setups based on rules  
✅ Simulate (paper-trade) performance  
✅ Explain recommendations in English  
✅ Alert via Telegram  
✅ Track risk metrics  
✅ Log everything for review  

---

## 🚀 Running the System

```bash
# Install dependencies
pip install -r requirements.txt

# Set up your secrets (.env file)
INDSTOCKS_TOKEN=your_24hr_token_from_api.indstocks.com
GEMINI_API_KEY=your_google_gemini_key
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_CHAT_ID=your_chat_id

# Run one cycle (collect data, analyze, recommend)
python -m app.main

# Run continuously during market hours
python -m app.main --daemon

# Print current configuration
python -m app.main --print-config
```

---

## 💡 Key Takeaways

1. **Real data?** YES — uses live APIs, not simulated/backtest data
2. **For traders?** NO — for quantitative researchers testing hypotheses
3. **Safe?** YES — no real money is touched; paper-trades only
4. **Deterministic?** MOSTLY — rules-based strategies with AI explanations, not AI-driven
5. **For non-traders?** THIS GUIDE helps! 📖

---

## 📚 Glossary

| Term | Definition |
|------|-----------|
| **API** | Application Programming Interface - way to fetch data programmatically |
| **Backtest** | Test strategy on historical data (past prices) |
| **Bid-Ask Spread** | Difference between buy & sell prices |
| **Book Run** | Track current positions and trades |
| **Breakout** | Price breaks above resistance level |
| **Bull/Bear** | Bull = optimistic (buy), Bear = pessimistic (sell) |
| **Correlation** | How two things move together |
| **Drawdown** | Peak-to-trough decline in account value |
| **Greeks** | Delta, Gamma, Theta, Vega - option sensitivities |
| **Hedge** | Offsetting trade to reduce risk |
| **IST** | Indian Standard Time (UTC+5:30) |
| **Liquidity** | How easily an asset can be bought/sold |
| **Lot Size** | Minimum contract multiplier (NIFTY = 75 shares) |
| **Market Depth** | Number of buy/sell orders at each price |
| **Moneyness** | How far in/out of profit an option is |
| **Moving Average** | Average price over N periods |
| **Pip** | Smallest price movement |
| **Slippage** | Difference between expected vs actual execution price |
| **Spread** | Difference between bid & ask prices |
| **Volatility** | How much price swings (high = big moves) |
| **Whitelist** | List of instruments we trade (not all 50 NIFTY stocks) |
| **YTD** | Year-to-date (from Jan 1 to now) |

---

## 🤔 Common Questions

**Q: Will this make me rich?**  
A: No. This is a *research tool*, not a money printer. Paper-trade results ≠ real money results.

**Q: Can I use this live with real money?**  
A: Not yet. The system must be extended to connect to a real broker API. Currently it only paper-trades.

**Q: What if the data is wrong?**  
A: The system marks it as INVALID/WARNING and won't generate signals. Failures are logged.

**Q: How often does it check the market?**  
A: Every ~5 seconds during market hours (9:15 AM - 3:30 PM IST for options).

**Q: Can I change the strategies?**  
A: Yes! Edit `app/strategies/implementations.py` and add your own logic.

**Q: Where does it save snapshots?**  
A: Dev = RAM, Prod = Google Cloud Firestore (see config/default.yaml).

---

Good luck! 🎯
