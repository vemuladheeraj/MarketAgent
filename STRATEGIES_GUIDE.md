# Strategies Guide: Understanding MarketAgent Trading Ideas

> **This guide explains how strategies work, with real examples for non-traders.**

---

## What is a Strategy?

A **strategy** is a deterministic rule system that detects trading opportunities.

Think of it like a **recipe for bread**:
- **Input**: Flour, water, salt, yeast
- **Process**: Mix, knead, proof, bake
- **Output**: Bread

Similarly, a trading strategy:
- **Input**: Market data (price, indicators, OI, regime)
- **Process**: Check conditions using mathematical rules
- **Output**: Trading idea (entry, stop-loss, target) or "no signal"

**Key difference from AI**: Strategies don't use neural networks or magic. They use explicit, testable rules that you can understand and audit.

---

## The Strategy Evaluation Flow

```
┌─────────────────────────────────────────────────────────────┐
│ MARKET DATA ARRIVES                                         │
│ NIFTY: 25432 | RSI: 68 | Regime: STRONG_UPTREND | OI: ↑    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ STRATEGY SELECTION                                          │
│ "Which strategies are active right now?"                    │
│                                                              │
│ ✓ OpeningRangeBreakout (prefers UPTREND)                   │
│ ✓ VWAPMomentum (prefers UPTREND)                           │
│ ✓ TrendContinuation (prefers UPTREND)                      │
│ ✗ SupportResistanceReversal (prefers RANGE, not UPTREND)   │
│ ✗ BearPutSpread (prefers RANGE or DOWNTREND)              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ FOR EACH ACTIVE STRATEGY:                                  │
│                                                              │
│ 1️⃣  Check has_setup()                                      │
│     "Are the conditions present?"                           │
│     OpeningRangeBreakout: Price > opening high? YES ✓      │
│                                                              │
│ 2️⃣  Calculate entry, stop, target                          │
│     Entry: 25432                                            │
│     Stop: 25200 (opening low)                               │
│     Target: 25662 (entry + 2× risk)                         │
│                                                              │
│ 3️⃣  Rate factors (trend, volume, momentum, etc.)           │
│     Trend: 0.8 (strong) | Volume: 0.6 (ok) | Momentum: 0.9 │
│                                                              │
│ 4️⃣  Calculate expected value                               │
│     EV = (0.5 × 230) - (0.5 × 232) = 115 - 116 = -1        │
│     ⚠️  Negative EV (risky, but margin is close)           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ SIGNAL SCORER                                               │
│                                                              │
│ Rating: (0.8 trend + 0.6 volume + 0.9 momentum) / 3 = 0.77  │
│ ↓                                                           │
│ Quality: STRONG_BUY (score > 0.75)                          │
│ ↓                                                           │
│ Risk check:                                                 │
│  ✓ Risk ₹232 < Account risk limit (₹5,000)                │
│  ✓ Position size: 21 contracts (within limits)             │
│  ✓ No red flags in data quality                             │
│ ↓                                                           │
│ RECOMMENDATION GENERATED                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ TRADER SEES:                                                │
│                                                              │
│ 🎯 BUY NIFTY 25500 CALL @ ₹150                             │
│    • Entry: 25432                                           │
│    • Stop Loss: 25200                                       │
│    • Target: 25662                                          │
│    • Risk/Reward: 1:1 (232 risk for 230 profit)            │
│    • Position Size: 21 contracts                            │
│    • Confidence: STRONG_BUY                                 │
│                                                              │
│ 💭 Explanation: "Opening range breakout in confirmed       │
│    strong uptrend with good volume support."               │
│                                                              │
│ 👉 ACTION: Trader manually decides to ACCEPT/REJECT        │
│    (System does NOT place the trade)                        │
└─────────────────────────────────────────────────────────────┘
```

---

## The 7 Built-In Strategies (Explained Simply)

### **1️⃣ Opening Range Breakout Strategy**

**Concept**: Price breaks above the first 30 minutes of trading.

**When to expect it**: UPTREND regimes

**How it works**:
```
9:15 AM: Market opens
  ├─ High: ₹25,500
  └─ Low: ₹25,350

10:45 AM: Price at ₹25,520
  → ✓ Above opening high (25,500)
  → ✓ Strategy triggers!

Entry: 25,520
Stop-Loss: 25,350 (opening low)
Risk: 170 points
Target: 25,520 + (2 × 170) = 25,860
```

**Why it works**: Professional traders often buy right after market opens. If price breaks above the opening range, momentum might continue.

**Trader perspective**: "The market opened but didn't go too far. Now it's breaking out — should I jump in?"

---

### **2️⃣ VWAP Momentum Strategy**

**Concept**: Price above VWAP (Volume Weighted Average Price) with good momentum.

**What is VWAP?**: Average price, weighted by how much volume traded at each level. Gives more weight to prices where more people traded.

**When to expect it**: UPTREND regimes

**How it works**:
```
Current VWAP: ₹25,400
Current Price: ₹25,432
  → Price > VWAP ✓

RSI 14: 65 (momentum indicator, >50 = bullish)
  → Bullish momentum ✓

ATR 14: ₹145 (volatility measure)

Entry: 25,432
Stop-Loss: 25,432 - 145 = 25,287 (below ATR)
Target: 25,432 + (1.8 × 145) = 25,692
```

**Why it works**: VWAP acts like a "fair price" floor. When price holds above it with good momentum, buyers are in control.

**Trader perspective**: "Price is above where the smart money traded. Momentum is strong. Should I ride this up?"

---

### **3️⃣ Trend Continuation Strategy**

**Concept**: Price above 20-period simple moving average in an uptrend.

**What is SMA 20?**: Simple average of the last 20 candles. Smoother trend indicator.

**When to expect it**: UPTREND regimes

**How it works**:
```
SMA 20: ₹25,350
Current Price: ₹25,432
  → Price above SMA_20 ✓

Regime: STRONG_UPTREND ✓
ATR 14: ₹145

Entry: 25,432
Stop-Loss: min(SMA_20, close - ATR) = min(25,350, 25,287) = 25,287
Target: 25,432 + (2 × 145) = 25,722
```

**Why it works**: Trend lines (like SMA 20) act as support during uptrends. Price bouncing off them = buyers are still in control.

**Trader perspective**: "The trend is up. Price is above the trend line. Might go higher. Should I stay long?"

---

### **4️⃣ Support & Resistance Reversal Strategy**

**Concept**: Price near support level in a ranging market (not trending).

**What is Support?**: A price level where sellers historically stopped the fall.
**What is Resistance?**: A price level where buyers historically stopped the rise.

**When to expect it**: RANGE regimes (not trending)

**How it works**:
```
Regime: RANGE (not trending)
Support Level: ₹25,350
Current Price: ₹25,352
  → Price within 1% of support ✓

RSI 14: 35 (oversold, might bounce)
  → Oversold ✓

Entry: 25,352
Stop-Loss: 25,350 × 0.995 = 25,327
Target: 25,550 (resistance level)
```

**Why it works**: In range-bound markets, price bounces between support and resistance. Buying near support and selling near resistance captures these bounces.

**Trader perspective**: "Market's stuck between ₹25,300 and ₹25,550. Price hit bottom support. Should I buy the bounce?"

---

### **5️⃣ OI + Price Confirmation Strategy**

**Concept**: Price high AND high call open interest building up (bullish signal).

**What is OI Buildup?**: Traders opening NEW call contracts (bullish bet).

**When to expect it**: UPTREND regimes when OI is increasing

**How it works**:
```
Price: ₹25,432 (above SMA_20, RSI > 50)
  → Bullish technicals ✓

Call OI: 450,000 contracts (was 420,000 yesterday)
Change in Call OI: +30,000 ✓ (building up)

Put OI: 320,000 contracts (was 330,000 yesterday)
Change in Put OI: -10,000 (unwinding)

PCR: 0.71 (puts/calls < 1, bullish)

Entry: 25,432
Stop-Loss: 25,287 (technical support)
Target: 25,662
```

**Why it works**: When smart money buys calls AND price goes up, it's a confirmation that the move is real, not forced by short-covering.

**Trader perspective**: "Price went up AND traders are stacking calls. This looks serious. Should I follow?"

---

### **6️⃣ Bull Call Spread Strategy**

**Concept**: Buy a lower-strike call, sell a higher-strike call (reduce cost, limit profit).

**When to expect it**: Mild uptrends where we want to reduce risk

**How it works**:
```
Market: Moderately bullish (not explosive)
  
Buy 25,400 CALL @ ₹200
Sell 25,500 CALL @ ₹80
  → Net cost: ₹120

If price reaches 25,500:
  → Buy side profit: ₹100
  → Sell side loss: -₹100
  → Total profit capped at ₹120 (your initial cost)

If price falls to 25,350:
  → Both expire worthless
  → Total loss: ₹120 (your initial cost)

Risk: ₹120
Reward: Max ₹80 profit (67% return, but limited)
```

**Why it works**: Spreads reduce the premium paid. Useful when you're bullish but not explosive-move bullish.

**Trader perspective**: "I think it'll go up, but not by much. Let me reduce my cost by selling a higher call."

---

### **7️⃣ Bear Put Spread Strategy**

**Concept**: Sell a lower-strike put, buy a higher-strike put (collect premium, limit loss).

**When to expect it**: Mild downtrends or range-bound conditions

**How it works**:
```
Market: Mildly bearish
  
Sell 25,400 PUT @ ₹120
Buy 25,300 PUT @ ₹40
  → Net credit: ₹80

Best case (price stays above 25,400):
  → Both expire worthless
  → Keep full premium: ₹80 profit

Worst case (price falls to 25,300):
  → Full loss: ₹20 (capped by bought put)

Risk: ₹20
Reward: ₹80 premium (4:1, but capped)
```

**Why it works**: Premium seller strategy. You're betting price won't fall below support. Keep the premium if right, defined loss if wrong.

**Trader perspective**: "Price won't fall much. Let me sell puts and collect premium. The bought put limits my loss if I'm wrong."

---

## How Strategies Score Signals

After generating a candidate, the **Scorer** rates it:

```
┌──────────────────────────────────────────┐
│ STRATEGY CANDIDATE GENERATED              │
│ Entry: 25432, SL: 25200, Target: 25662   │
│ EV: -1 (slightly negative)                │
│ Factors: trend=0.8, volume=0.6, momentum=0.9
└──────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│ SCORER EVALUATES                          │
│                                           │
│ 1. Data Quality Check                     │
│    └─ All quotes VALID? YES ✓            │
│                                           │
│ 2. Risk Gates                             │
│    └─ Risk ₹232 < ₹5,000 limit? YES ✓    │
│    └─ Position size reasonable? YES ✓    │
│                                           │
│ 3. Factor Score                           │
│    └─ (0.8 + 0.6 + 0.9) / 3 = 0.77      │
│                                           │
│ 4. EV Check                               │
│    └─ EV -1 (close to zero, ok)          │
│       After costs: EV likely negative     │
│       But margin tight; still worth eval. │
└──────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│ RATING ASSIGNED                           │
│                                           │
│ ✅ STRONG_BUY (0.77 score)                │
│    All lights green; solid opportunity    │
│                                           │
│ Other ratings possible:                   │
│ 🟢 BUY: Good setup, lower confidence      │
│ 🟡 CAUTION: Mixed signals, risky          │
│ 🔴 NO_TRADE: Data too poor, skip this     │
└──────────────────────────────────────────┘
```

---

## Practical Example: Real Trading Day

### **10:30 AM, Market Session**

**Market Snapshot Received:**
```
NIFTY Close: ₹25,432 (↑ ₹120)
Opening Range High: ₹25,500
Opening Range Low: ₹25,350
SMA 20: ₹25,350
RSI 14: 68
ATR 14: ₹145
VWAP: ₹25,400
Regime: STRONG_UPTREND (ADX=42, moving averages aligned)
VIX: 14.2 (calm)
Breadth: 1,600 up, 800 down (bullish)
```

### **Strategy Evaluation (Each Strategy Checks Itself):**

**Strategy 1: OpeningRangeBreakout**
- is_applicable? UPTREND regime? YES ✓
- has_setup? Price (25,432) > opening high (25,500)? NO ✗
- → NO SIGNAL for this strategy

**Strategy 2: VWAPMomentum**
- is_applicable? UPTREND regime? YES ✓
- has_setup? Price > VWAP (25,432 > 25,400)? YES ✓ AND RSI > 50 (68)? YES ✓
- → SETUP FOUND!
- Entry: 25,432
- Stop-Loss: 25,432 - 145 = 25,287
- Target: 25,432 + (1.8 × 145) = 25,692
- Factor scores: trend=0.8, momentum=0.9, volume=0.5
- EV = (0.5 × 260) - (0.5 × 145) = 130 - 73 = +57 ✓
- → CANDIDATE CREATED

**Strategy 3: TrendContinuation**
- is_applicable? UPTREND regime? YES ✓
- has_setup? Price > SMA_20 (25,432 > 25,350)? YES ✓
- → SETUP FOUND!
- Entry: 25,432
- Stop-Loss: min(25,350, 25,432 - 145) = 25,287
- Target: 25,432 + (2 × 145) = 25,722
- Factor scores: trend=1.0, momentum=0.5
- EV = (0.5 × 290) - (0.5 × 145) = 145 - 73 = +72 ✓
- → CANDIDATE CREATED

**Strategies 4-7**: RANGE/DOWNTREND specific → Not applicable today

### **Scorer Evaluation:**

**VWAP Momentum Signal:**
- Quality: VALID ✓
- Factor score: (0.8 + 0.9 + 0.5) / 3 = 0.73
- Risk check: ✓ Within limits
- EV: +57 ✓
- → Rating: **STRONG_BUY** 🟢

**Trend Continuation Signal:**
- Quality: VALID ✓
- Factor score: (1.0 + 0.5) / 2 = 0.75
- Risk check: ✓ Within limits
- EV: +72 ✓
- → Rating: **STRONG_BUY** 🟢

### **Trader Notification (via Telegram):**

```
📊 MARKET ALERT (10:30 AM IST)

🎯 STRONG_BUY SIGNALS GENERATED (2 strategies)

1️⃣ VWAP Momentum
   Entry: 25,432
   Stop: 25,287
   Target: 25,692
   Risk/Reward: 1:1.78
   
2️⃣ Trend Continuation
   Entry: 25,432
   Stop: 25,287
   Target: 25,722
   Risk/Reward: 1:2.0

📈 Market: STRONG UPTREND | VIX: 14.2 (calm)
```

**Trader Decision:**
- Reads both signals
- Both agree on direction (LONG) and entry (25,432)
- Opens account manually
- Buys 21 NIFTY 25500 CALL contracts @ ₹150
- Sets stop at 25,287
- Sets target at 25,692
- System tracks paper trade performance

---

## Key Takeaways

1. **Strategies are deterministic**: They follow explicit rules, not AI magic
2. **Multiple strategies can fire**: Different strategies might generate different ideas on the same day
3. **Signals get scored**: Raw signals are rated (NO_TRADE → STRONG_BUY)
4. **Risk is always checked**: Position size, account risk limits, data quality
5. **Traders decide**: System recommends; trader executes (or skips)
6. **Paper-trading tracks results**: See which signals would have worked
7. **No real money is touched**: Until you decide to use this with a real broker API

---

## Common Questions

**Q: Which strategy should I use?**  
A: All 7 run simultaneously. The scorer picks the best ones based on factor scores and EV.

**Q: Can I create my own strategy?**  
A: Yes! Extend `BaseStrategy` in `app/strategies/implementations.py` and implement the 5 methods:
   - `has_setup()` — Check your condition
   - `calculate_direction()` — Return LONG or SHORT
   - `calculate_stop_loss()` — Set your stop
   - `calculate_targets()` — Set your profit targets
   - `factor_scores()` — Rate the setup quality

**Q: What if I disagree with the scorer's rating?**  
A: You're the final decision maker. You can skip any recommendation. The paper-trading log shows which you would've done well on.

**Q: Do these strategies work?**  
A: Unknown! They're research templates. Phase 14 includes backtesting to find the edge.

**Q: Why is EV sometimes negative?**  
A: Before costs. Risk/reward might not cover brokerage, taxes, slippage. Risk engine filters these out.

---

Happy trading! 🚀
