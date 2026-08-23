# Indian Market Intelligence & Options Research Agent

A personal, quantitative research and decision-support system for the Indian
equity and derivatives markets (NSE/NIFTY/BANKNIFTY). Built to *test whether an
edge exists* — not to promise one.

> **Critical rule**: This system is a research tool. It does **not** place real
> trades (and never will in v1), does **not** fabricate market data or results,
> and does **not** claim profitability. Backtested, simulated or paper-traded
> numbers are research artifacts only.

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

## Phase 1 delivery — foundation

This repository implements **Phase 1 only** (incremental development is a hard
requirement — see the roadmap below). Phase 1 delivers:

1. **Central configuration system** — validated, secret-free-by-construction.
   YAML for defaults (`config/default.yaml`), environment / `.env` for secrets
   (`.env.example`), merged and validated through Pydantic
   (`app/config/settings.py` + loader).
2. **Core domain models** — strongly-typed, strictly tz-aware (IST) containers:
   `Instrument`, `FutureContract`, `OptionContract`, `MarketCandle`,
   `MarketQuote`, `OptionChainSnapshot`, `MarketSnapshot`, `BreadthSnapshot`,
   `SystemEvent`, `Alert`, plus all shared enums (`app/models/`). Pricing
   invariants (OHLC relationships, bid ≤ ask, positive strikes) are enforced at
   model construction.
3. **Logging**: structured `EVENT=...` observability on the `market.*` logger
   tree, console + optional rotating file (`app/logging/`).
4. **Application runner**: config → validation → startup → shutdown lifecycle
   (`app/orchestration/runner.py`), CLI entry `python -m app.main`.
5. **Package scaffolding**: the complete target tree (`data/`, `analysis/`,
   `strategies/`, `risk/`, `backtesting/`, `paper_trading/`, `ai/`,
   `notifications/`, `storage/`, `research/`, `tests/`) is in place as empty
   packages. Implementations arrive in the phases that use them — no fake
   placeholder logic.
6. **Unit tests**: 54 tests covering config, models, logging, and the runner.
   Deterministic fixtures only; no live data.

**What's NOT here yet** (by design): market data providers, analysis engines,
strategies, backtesting, AI, persistence, notifications.

---

## Project structure (Phase 1)

```
app/
    main.py            # CLI entry: python -m app.main [--config ...] [--env-file ...]
    config/settings.py # Settings tree + YAML/env loader (fully validated)
    models/            # domain models + enums + IST time helpers
    logging/           # structured market.* logging + log_event(...)
    orchestration/     # MarketAgentApplication lifecycle
    data/  analysis/  strategies/  scoring/  risk/
    backtesting/  paper_trading/  ai/  notifications/  storage/   (scaffolds)
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
  (sum = 100) and score→classification bands, provider/gemini/telegram/
  firestore placeholders.
- **Secrets** are read only from the environment / `.env`. Copy
  `.env.example` → `.env` to configure them. `.gitignore` guards `.env*` and
  credential files. Validation rejects `production` when required secrets are
  missing.
- All timestamps are tz-aware and canonicalised to IST (`Asia/Kolkata`)
  at model construction.

Environment overrides are declaratively mapped in `ENV_OVERRIDES`
(`app/config/settings.py`), e.g. `DATA_PROVIDER -> provider.name`,
`FIREBASE_PROJECT_ID -> firestore.project_id`.

---

## Running locally

```powershell
cd d:\DheerajAppWorks\Repos\MarketAgent

# 1) create a venv + install dependencies (Phase 1 is intentionally light)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2) run the Phase-1 application
python -m app.main                   # start -> validate -> shutdown
python -m app.main --print-config    # just verify the effective config

# 3) run the test suite
python -m pytest -q                  # expects 54 passed

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
- **Models**: OHLC invariants, bid ≤ ask, positive strikes, zero/negative
  rejection, tz-aware enforcement, UTC→IST canonicalisation, option-chain
  expiry ordering, PCR math, option key derivation.
- **Logging/runner**: handler wiring, structured event format, file logging,
  startup/shutdown, CLI exit codes, and a guard ensuring config summaries never
  contain secrets.

Later phases will add gold-standard indicator cross-validation (Phase 4),
no-look-ahead backtest audits (Phase 9), and provider mock contracts.

---

## Roadmap (incremental, evidence-gated)

| Phase | Focus | Evidence gate |
| ----- | ----- | ------------- |
| **1** ✅ done | Foundation: config, models, logging, runner | 54 unit tests pass; CLI run clean |
| 2 | Market data: provider abstraction, mock/replay, normalisation, DQ validator | VALID/WARNING/INVALID semantics covered by tests |
| 3 | Firestore repository + snapshot storage | integration tests against emulator/mock |
| 4 | Technical analysis: indicators, market structure | indicators match reference calculations |
| 5 | Options analysis: chain, OI, PCR, IV, Greeks | Greeks verified against known references |
| 6 | Market regime classifier | deterministic regime labels on fixture data |
| 7 | Strategy framework + signal scoring | per-strategy candidate tests |
| 8 | Risk engine: position sizing, cost model, EV | correct position sizing demonstrated |
| 9 | Backtesting: simulation, metrics, cost model | zero look-ahead demonstrated |
| 10 | Walk-forward validation / robustness | out-of-sample degradation reporting |
| 11 | Paper trading lifecycle | SIGNAL→…→RESULT lifecycle tests |
| 12 | Gemini contextual layer | structured outputs only, no fabricated numbers |
| 13 | Telegram commands + alerts | command tests with mocked Bot API |
| 14 | Always-on runtime: scheduler, recovery, monitoring | graceful-failure tests |

---

## Safety & ethics

- **No real trades — ever, in v1.** Operation modes are analysis, research,
  paper-trading, and alerting.
- **`NO_TRADE` is a successful outcome**; the system optimises for quality of
  trades over quantity.
- No strategy is assumed profitable because a backtest looks good. Profitability
  must be demonstrated: positive expectancy, positive profit factor, controlled
  drawdown, out-of-sample results, walk-forward stability, realistic
  transaction costs, across multiple regimes.
- No fabricated results: unavailable external data degrades to an explicitly
  labelled mock/replay provider for development and testing only.

*This software is for research and education. Nothing here is financial advice.*