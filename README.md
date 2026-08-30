# MarketAgent — Your Indian Options Trading Companion

A personal, quantitative research and decision-support system for the Indian
equity and derivatives markets (NSE/NIFTY/BANKNIFTY). Built to *test whether an
edge exists* â€” not to promise one.

> **How it works**: MarketAgent is your present-moment trading companion. It
> tells you what the quant model would do *right now* — direction, the exact
> option contract (e.g. `NIFTY 24750CE`), premium entry/stop/targets, and
> position size — but it does **not** place trades. You execute manually in
> your broker app. It does **not** fabricate market data or results, and does
> **not** claim profitability. Paper-traded numbers are research artifacts
> only.

---

## Design philosophy: two layers

| Layer | Responsibility |
| ----- | -------------- |
| **Quantitative layer** (deterministic, testable) | Market data, indicators, options maths, market structure/regime, strategy evaluation, backtesting, expected value, risk, position sizing |
| **AI layer** (Gemini, advisory only) | Explains quantitative results, interprets news, finds contradictions, summarises market conditions, answers natural-language questions |

Gemini **never** invents data, overrides risk controls, overrides
deterministic strategy rules, or places trades. Every quantitative claim it
makes must be grounded in the structured data the system supplies.

---

## Current Delivery

This repository contains the complete, verified implementation for **Phases 1-14**,
constituting the full specification of the Indian Market Intelligence & Options Research Agent.

### Phase 1 - Foundation

- Central configuration system with YAML defaults, environment secret loading,
  and Pydantic validation.
- Core domain models with IST-aware timestamps and pricing invariants.
- Structured `market.*` logging and a basic application lifecycle runner.
- Target project structure with future-phase packages clearly left as scaffolds.
- Unit tests for configuration, models, logging, and runner behavior.

### Phase 2 - Market Data

- Live `indstocks` and `nse` providers for quotes, candles, option chains, futures,
  breadth, VIX, and FII/DII flows.
- Normalizers from provider payloads into internal Pydantic models.
- Data-quality validator with `VALID` / `WARNING` / `INVALID` reports.
- Market snapshot collector that records provider failures as quality metadata.

### Phase 3 - Storage

- Repository abstraction.
- Deterministic in-memory repository for tests and development.
- Firestore repository adapter with lazy client creation.
- Collection-name mapping for the Firestore collections in the specification.

### Phase 4 - Technical Analysis

- SMA, EMA, VWAP, RSI, MACD, ROC, ATR, ADX, historical volatility,
  Bollinger bands, Supertrend, relative volume, and volume-spike detection.
- Price-structure helpers for previous/weekly levels, support/resistance,
  opening range, breakout/breakdown, and gap detection.
- `TechnicalAnalyzer` for deterministic `TechnicalIndicators` snapshots.

### Phase 5 - Options Analysis

- Black-Scholes-Merton pricing, Greeks, and bisection implied volatility.
- OI totals, PCR, max-OI strikes, OI concentration, call resistance,
  put support, and aggregate change in OI.
- Strike-level moneyness and OI buildup/unwinding classification using explicit
  option price-change input.
- ATM and near-strike structure plus IV expansion/contraction checks.

### Phase 6 - Market regime

- Rule-based `RegimeClassifier` using ADX, moving averages, Supertrend,
  directional movement, historical volatility, India VIX, and breadth.
- Labels: strong/up/down trend, range, high/low volatility, event-driven,
  uncertain. Extreme VIX/HV or `event_risk` can override a trend label.
- Gemini is not used to classify regime.

### Phase 7 - Strategy framework and signal scoring

- Common strategy contract: applicability, candidate generation, entry/stop/
  targets/invalidation, pre-cost expected value, and explanation.
- Initial strategies: opening-range breakout, VWAP momentum, trend
  continuation, support/resistance reversal, OI+price confirmation, breakout
  with volume, mean reversion, bull call spread, bear put spread.
- Strategies are gated by preferred regimes; they are not blindly all enabled.
- Deterministic weighted scorer (weights sum to 100) with NO_TRADE through
  EXCEPTIONAL bands. INVALID data cannot produce an accepted signal.
- Candidate win-probability is an uninformed prior (0.5), not a calibrated
  edge estimate. Options-spread strategies emit underlying reference levels,
  not filled option-leg prices.

### Phase 8 - Risk engine, costs, expected value, and snapshot persistence

- Indian transaction-cost model: brokerage, STT (buy/sell), GST on
  (brokerage + exchange + SEBI), exchange, SEBI, buy-side stamp duty,
  slippage, and bid/ask spread. Round-trip totals are explicit and
  reproducible.
- Position size is the largest lot-multiple whose stop-out loss *including
  costs* stays inside `account_size * risk_per_trade_pct`. Quantity is never
  an arbitrary recommendation.
- Expected value is reported as gross and net (after costs). Probability is
  still the candidate prior; a positive net EV is not a claim of edge.
- Risk filters: emergency disable, daily loss cap, max trades/day, max
  concurrent paper positions, min R:R, min net EV, consecutive-loss cooldown.
  A storage failure marks the risk book unavailable and **rejects** new paper
  entries rather than sizing unsafely.
- `MarketStore` persists market snapshots, option chains, signals, regimes,
  risk assessments, risk state, and system events. If `FIREBASE_PROJECT_ID`
  is set, the Firestore adapter is used; otherwise an in-memory store is used.
  The process collects live market snapshots from the configured provider and
  writes them to the configured store.

### Phase 9 - Backtesting Engine & Performance Evaluation

- Deterministic event-driven bar-by-bar backtester (`BacktestEngine`) strictly
  enforcing **zero lookahead bias**: strategy evaluations at time $t$ only see
  candles $C_{0 \dots t}$.
- Rigorous trade lifecycle: entry scheduled for next-bar open (or current close),
  target profit exits, stop-loss exits, max holding bars (time exit), and
  end-of-series liquidations.
- Intrabar exit modeling with **pessimistic conflict resolution** (if both target
  and stop loss are within candle $[Low, High]$, stop loss is triggered to prevent
  optimistic backtest bias) and gap slippage handling.
- Full Indian transaction cost and slippage deduction for every round trip
  via `TransactionCostModel`, reporting both Gross P&L and Net P&L.
- Dynamic lot-based position sizing and risk budget controls via `RiskEngine`
  and `PositionSizer`.
- Complete statistical and financial performance suite (`calculate_performance`):
  total trades, win rate, average win/loss, profit factor, average R-multiple,
  expectancy, high-water mark peak-to-trough max drawdown ($ and %),
  annualized Sharpe and Sortino ratios, winning/losing streaks, and
  regime-wise performance attribution.
- `BacktestRunner` for automated multi-strategy comparison and formatted
  reporting tables.

### Phase 10 - Walk-Forward Validation & Anti-Overfitting

- `WalkForwardSplitter` for rolling sliding windows and expanding (anchored) chronological train/test partitions with zero data leakage.
- `WalkForwardEngine` for out-of-sample robustness evaluation, calculating Walk-Forward Efficiency (WFE), win rate retention, P&L retention, consistency score, and automated overfit suspicion flags.

### Phase 11 - Paper Trading Lifecycle & Continuous Monitoring

- `PaperTradingEngine` implementing the live paper trade state machine (`SIGNAL -> PAPER_ENTRY -> MONITOR -> EXIT -> RESULT`).
- Real-time tick & intrabar quote updates, dynamic MAE/MFE excursion tracking, stop-loss / target triggering, round-trip Indian cost deductions, and atomic `RiskState` synchronization.
- `PaperPerformanceTracker` for rolling performance metrics and automated strategy degradation alerts.

### Phase 12 - Gemini Contextual Reasoning & Contradiction Detection

- `ContradictionDetector` for cross-layer conflict identification (e.g. Bullish Price vs Call Resistance OI, Breakout without Volume Confirmation, Price vs Breadth Divergence).
- `GeminiClient` providing strictly structured contextual market analysis, grounded only in verified quantitative data without number fabrication, with robust fail-soft offline fallbacks.
- `NewsContextManager` for macro/market news ingestion and sentiment aggregation.

### Phase 13 - Telegram Alerts & Bot Commands

- Interactive Telegram command handler (`/status`, `/signals`, `/nifty`, `/banknifty`, `/options`, `/vix`, `/watchlist`, `/papertrades`, `/performance`, `/analysis`).
- Proactive formatted alert dispatchers (`notify_market_open`, `notify_signal`, `notify_exit`, `notify_daily_report`, `notify_options_summary`).
- Fail-soft HTTP Telegram client ensuring notifications never crash trading pipelines.

### Phase 14 - Always-On Runtime, Scheduler & End-to-End Pipeline

- `MarketSessionScheduler` managing IST market session awareness (pre-open, regular, post-market, closed).
- `MarketIntelligencePipeline` wiring data collection, validation gating, technical analysis, options intelligence, regime detection, strategy scoring, risk assessment, paper execution, Gemini reasoning, and Telegram alerts into a single unified cycle.
- Graceful daemon lifecycle with signal handling (`SIGINT`, `SIGTERM`), CLI flags (`--daemon`, `--print-config`), and 100% test coverage across 218 unit and integration tests.

### Phase 16 - Trade Brief Companion (present-moment decision support)

- `TradeAdvisor` fuses the best risk-approved signal, the live option chain,
  and the risk-engine sizing into one human answer per symbol per cycle:
  **BUY** (with the exact contract, e.g. `NIFTY 24750CE`), or an explicit
  **WAIT** with the concrete reason. Standing aside is a first-class
  recommendation.
- LONG view maps to the nearest-ATM CALL, SHORT to the nearest-ATM PUT
  (`advisor.strike_offset` moves further OTM). Index-level risk/reward is
  translated into premium space using the contract delta, with a
  premium/spot-ratio fallback that is flagged as a warning on the brief.
- Briefs carry premium entry/stop/targets, lots, risk and reward in INR, net
  EV after costs, score, regime, OI context, spread/IV warnings, and a
  validity window (`advisor.validity_minutes`).
- Persistence: `tradeBriefs/current_<SYMBOL>` is refreshed every cycle for the
  dashboard; history rows are written only when the actionable setup changes
  so fast daemon cycles do not flood Firestore.
- Telegram: `notify_trade_brief` pushes a new brief once per setup, suppressed
  for `advisor.telegram_dedupe_minutes` — no 5-second alert spam.
- No auto-execution anywhere: the human reads the brief and bids manually.

---

## Project structure

```
app/
    main.py            # CLI entry: python -m app.main [--config ...] [--env-file ...]
    config/settings.py # Settings tree + YAML/env loader (fully validated)
    models/            # domain models + enums + IST time helpers
    logging/           # structured market.* logging + log_event(...)
    orchestration/     # MarketAgentApplication lifecycle
    data/  analysis/  storage/     # implemented through current phases
    analysis/regime/   # deterministic classifier
    strategies/        # contract, nine initial strategies, engine
    scoring/           # weighted signal scorer
    risk/              # costs, position sizing, EV, risk filters
    storage/           # in-memory + Firestore repositories + MarketStore
    backtesting/  paper_trading/  ai/  notifications/   # later phases
config/default.yaml    # non-secret defaults
scripts/               # run_test.ps1 / run_app.ps1
tests/                 # unit tests (deterministic fixtures only)
research/              # notebooks/, experiments/
.env.example
.gitignore
requirements.txt
pytest.ini
```

## Configuration

```
category            | source            | examples
--------------------+-------------------+----------------------------------
secrets             | env only          | GEMINI_API_KEY, TELEGRAM_BOT_TOKEN,
                    |                   | FIREBASE_CREDENTIALS_PATH
all other settings   | config/*.yaml    | sessions, instruments, risk, costs
```

- **Non-secrets** live in `config/default.yaml`: trading sessions (equity cash,
  derivatives, pre-open), watchlist instruments (NIFTY, BANKNIFTY), risk
  parameters, the Indian transaction-cost model, signal scoring weights
  (sum = 100) and scoreâ†’classification bands, provider/gemini/telegram/
  firestore placeholders.
- **Secrets** are read only from the environment / `.env`. Copy
  `.env.example` â†’ `.env` to configure them. `.gitignore` guards `.env*` and
  credential files. Validation rejects `production` when required secrets are
  missing.
- All timestamps are tz-aware and canonicalised to IST (`Asia/Kolkata`)
  at model construction.

Environment overrides are declaratively mapped in `ENV_OVERRIDES`
(`app/config/settings.py`), e.g. `DATA_PROVIDER -> provider.name`,
`INDSTOCKS_ACCESS_TOKEN -> provider.params.access_token`,
`DAEMON_INTERVAL_SECONDS -> orchestration.daemon_interval_seconds`,
`FIREBASE_PROJECT_ID -> firestore.project_id`.

---

## Running locally

```powershell
cd d:\DheerajAppWorks\Repos\MarketAgent

# 1) create a venv + install dependencies
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2) run the application lifecycle
python -m app.main                   # start -> collect one snapshot -> persist -> shutdown
python -m app.main --print-config    # just verify the effective config

# Persistence: leave FIREBASE_PROJECT_ID empty for in-memory storage.
# To write to Firestore, set FIREBASE_PROJECT_ID and FIREBASE_CREDENTIALS_PATH
# in `.env` (service-account JSON). Collections used: marketSnapshots,
# optionSnapshots, signals, marketRegimes, riskAssessments, riskState,
# systemEvents, tradeBriefs.

# 3) run the test suite
python -m pytest -q

# 4) convenience wrappers
.\scripts\run_app.ps1
.\scripts\run_test.ps1
```

---

## Testing strategy

- Unit tests use **deterministic fixtures only** (`tests/conftest.py`) and
  inject an isolated `environ`, so a developer's shell can never leak secrets
  into a test run.
- **Config**: default YAML load, env-var overrides, weights-must-sum-to-100,
  session time format, timezone existence, production-secret gate, missing
  config file handling.
- **Models**: OHLC invariants, bid â‰¤ ask, positive strikes, zero/negative
  rejection, tz-aware enforcement, UTCâ†’IST canonicalisation, option-chain
  expiry ordering, PCR math, option key derivation.
- **Market data**: live provider contracts, normalizers, data-quality reports,
  and collector failure handling.
- **Technical/options analysis**: deterministic indicators, market structure,
  Black-Scholes pricing, Greeks, IV, OI summaries, and strike-level option
  structure.
- **Regime/strategies/scoring**: fixture-based regime labels, per-strategy
  candidate generation, regime gating, INVALID-data rejection, and score bands.
- **Risk**: zero-cost position size equals budget / per-unit risk; costs reduce
  quantity; lot multiples; transparent EV formula; filter rejections.
- **Storage**: in-memory repository, MarketStore persist/load, fail-soft
  Firestore errors, and repository factory behavior.
- **Logging/runner**: handler wiring, structured event format, file logging,
  startup/shutdown, CLI exit codes, and a guard ensuring config summaries never
  contain secrets.

Later phases will add no-look-ahead backtest audits, walk-forward validation,
paper-trading lifecycle tests, Gemini safety tests, and Telegram command tests.

---

## Roadmap (incremental, evidence-gated)

| Phase | Focus | Evidence gate |
| ----- | ----- | ------------- |
| **1** done | Foundation: config, models, logging, runner | config/model/runner tests |
| **2** done | Market data: provider abstraction, live NSE/INDstocks feeds, normalisation, DQ validator | provider/normalizer/validator/collector tests |
| **3** done | Firestore repository + snapshot storage | repository factory and memory repository tests; Firestore adapter is dependency-gated |
| **4** done | Technical analysis: indicators, market structure | indicator/analyzer tests |
| **5** done | Options analysis: chain, OI, PCR, IV, Greeks, structure | pricing/Greeks/IV/OI/strike analysis tests |
| **6** done | Market regime classifier | deterministic regime labels on fixture data |
| **7** done | Strategy framework + signal scoring | per-strategy candidate tests + score-band tests |
| **8** done | Risk engine: position sizing, cost model, EV, snapshot persist | position size = budget/R including costs; Firestore/memory store writes |
| **9** done | Backtesting: simulation, metrics, cost model | zero look-ahead demonstrated |
| 10 done | Walk-forward validation / robustness | out-of-sample degradation reporting |
| 11 done | Paper trading lifecycle | SIGNAL→…→RESULT lifecycle tests |
| 12 done | Gemini contextual layer | structured outputs only, no fabricated numbers |
| 13 done | Telegram commands + alerts | command tests with mocked Bot API |
| 14 done | Always-on runtime: scheduler, recovery, monitoring | graceful-failure tests |
| 15 done | Real-time Web Dashboard & Netlify Deployment | React + Tailwind + Firestore onSnapshot live monitoring |
| 16 done | Trade Brief companion: present-moment BUY/WAIT guidance on the exact option contract | advisor unit tests + pipeline integration test |

---

## Web Dashboard

The web interface is located in `web/` and connects directly to your Firebase Firestore database (`marketagent-9ea8f`) to display market snapshots, option chains, regime classifications, strategy signals, and Gemini AI analysis using live Firestore subscriptions.

The **Trade Brief card** at the top of the Overview tab is the companion answer: the exact option contract to bid (or an explicit WAIT), premium entry/stop/targets, lots, R:R, net EV, and the reasoning — refreshed live from `tradeBriefs/current_<SYMBOL>`.

> **Important:** The dashboard only displays data written by the backend agent to Firestore. Run the live agent (below) to see real, continuously-refreshed data.

### 1. Run the live agent (real-time data feed)
Start the always-on agent that fetches live market data and persists it to Firestore for the dashboard:
```powershell
# In .env set:
#   DATA_PROVIDER=indstocks
#   INDSTOCKS_ACCESS_TOKEN=<your 24h token from indstocks.com/app/api-trading/access-tokens>
.\scripts\run_live.ps1
```
This runs `python -m app.main --daemon`, which pulls **realtime** quotes (INDstocks WebSocket + REST), option chains, VIX/breadth (via NSE fallback), classifies the market regime, runs Gemini analysis, and persists everything to Firestore during NSE trading hours every **5 seconds** by default. Keep the terminal open.

**Data providers:** `indstocks` (recommended — free realtime API, needs INDstocks account + KYC + access token), `nse` (public NSE scrape, no auth).

### 2. Launch the dashboard locally
In a second terminal:
```powershell
cd web
npm run dev
```
Open **http://localhost:3000**.
The dashboard auto-updates in real time via Firestore `onSnapshot` listeners.

### Deploying to Netlify
1. Connect your repository to **[Netlify](https://app.netlify.com/)**.
2. Set **Base directory**: `web`
3. Set **Build command**: `npm run build`
4. Set **Publish directory**: `dist`
5. Netlify will build and deploy the dashboard instantly with zero server infrastructure needed.

---

## Safety & ethics

- **No real trades â€” ever, in v1.** Operation modes are analysis, research,
  paper-trading, and alerting.
- **`NO_TRADE` is a successful outcome**; the system optimises for quality of
  trades over quantity.
- **No auto-execution, ever.** The agent produces briefs, signals, paper trades
  and alerts; the human places every order manually in their broker app.
- No strategy is assumed profitable because a backtest looks good. Profitability
  must be demonstrated: positive expectancy, positive profit factor, controlled
  drawdown, out-of-sample results, walk-forward stability, realistic
  transaction costs, across multiple regimes.
- No fabricated results: if live market data is unavailable, the pipeline records
  explicit data-quality failures rather than inventing prices or signals.

*This software is for research and education. Nothing here is financial advice.*
