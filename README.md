# AlgoTrade AI — Production-Grade Multi-Strategy Algorithmic Trading Platform

AlgoTrade AI is an enterprise-grade quantitative trading workstation and algorithmic execution engine for Indian markets (NSE Cash Equities, Futures, Options, and Swing Trading).

Built with Python 3.12+, FastAPI, Streamlit, Plotly, Scikit-Learn, and Supabase PostgreSQL.

---

## 1. Key Architectural Capabilities

- **Unified Trading Workstation (12 Pages):** Real-time command center, interactive market terminal, strategy laboratory, ensemble consensus monitor, backtesting laboratory, paper trading workstation, portfolio & trade journal, options analytics, alert center, risk management center, integrations manager, and governance settings.
- **11+ Quantitative Strategy Registry:**
  - *Trend Following:* EMA Crossover, Supertrend (ATR dynamic trailing stops), ADX-MACD trend strength filter, Donchian Channel trend.
  - *Momentum:* Price-Volume Momentum & Relative Strength surge.
  - *Breakout:* Opening-Range Breakout (ORB) with volume expansion.
  - *Mean Reversion:* RSI Extreme reversion, Bollinger Bands reversion with statistical Z-scores.
  - *Swing Trading:* Multi-day trend pullback with ATR trailing stops.
  - *Options Desk:* Defined-risk Vertical Spreads (Bull Call, Bear Put, Straddles, Iron Condor) with Black-Scholes Greeks (Delta, Gamma, Theta, Vega) & payoff diagrams.
  - *Machine Learning / AI:* Random Forest regime classifier and calibrated probability estimator.
- **Central Risk Authority:** Strict pre-trade checks, per-trade risk budgets, 10% max single position notional, 1% daily portfolio loss halt, 5% peak-to-trough drawdown circuit breaker, NSE market hours enforcement (09:15 - 15:30 IST) with holiday calendar, and instantaneous emergency kill-switch.
- **Event-Driven Backtest Engine:** Chronological bar processing without lookahead leakage, modeling full Indian statutory transaction costs (Brokerage ₹20, STT, Exchange turnover charges, SEBI turnover fees, GST 18%, Stamp duty), slippage, automated stop loss/take profit, walk-forward out-of-sample validation, and Sharpe/Sortino/CAGR/drawdown performance reporting with CSV exports.
- **Simulated Paper Trading:** Realistic order fills with slippage, position tracking, cash balance, and state persistence across application restarts (`paper_trading_state.json` + SQLite/Supabase).
- **TradingView Integration:** Secure webhook receiver (`POST /webhooks/tradingview`) with HMAC/passphrase authentication, timestamp freshness checks (drift < 120s), and 24-hour event-ID replay protection.
- **DhanHQ Broker Adapter:** Official DhanHQ OpenAPI v2 client with automated sandbox simulation and strict server-side live execution safety gate.
- **Supabase Cloud Persistence:** Versioned SQL migrations (`001_core_schema.sql`, `002_platform_tables.sql`, `003_row_level_security.sql`) with Row Level Security (RLS) and automatic local SQLite fallback.
- **Alert & Notification Center:** In-app alert queue with unread badges, Telegram notifier, email dispatcher, and notification storm suppression.

---

## 2. Quick Start

### Windows PowerShell

```powershell
# Navigate to project directory
cd algotrade-ai

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install / update dependencies
pip install -e ".[test]"

# Copy environment configuration
Copy-Item .env.example .env

# Launch FastAPI backend service
uvicorn app.main:app --reload --port 8000

# In a separate terminal, launch Streamlit workstation
streamlit run app/ui/streamlit_app.py
```

### Linux / macOS

```bash
cd algotrade-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
cp .env.example .env

# Launch FastAPI backend service
uvicorn app.main:app --reload --port 8000

# In a separate terminal, launch Streamlit workstation
streamlit run app/ui/streamlit_app.py
```

- **Interactive API Docs:** `http://127.0.0.1:8000/docs`
- **Streamlit Quantitative Workstation:** `http://localhost:8501`

---

## 3. Running Automated Tests

Run the comprehensive test suite (44 automated unit, integration, and risk tests):

```bash
pytest -v
```

All tests pass in clean environments covering strategies, risk limits, market hours, backtesting, paper trading, options Greeks, TradingView webhooks, and DhanHQ integration.

---

## 4. Workstation Navigation (12 Modules)

1. **Overview:** Executive portfolio summary, equity curve, open positions, detected market regime, strategy status, and system health.
2. **Market Terminal:** Searchable NSE watchlist, candlestick charts with EMA 20/50, Bollinger Bands, Volume, and Level 2 depth simulation.
3. **Strategy Registry:** Inspect all 11+ algorithms, parameters, version history, and interactive signal testing workbench.
4. **Ensemble Monitor:** Real-time signal feed, regime classification, voting matrix, conflict resolution, and net edge estimation.
5. **Backtesting Laboratory:** Historical data import, CSV upload, slippage/charge configuration, equity curves, trade logs, and walk-forward validation.
6. **Paper Trading:** Manual order ticket, simulated execution with slippage & taxes, active positions, and one-click squaring off.
7. **Portfolio & Positions:** Total capital allocation, margin utilized, closed trades history, and trade journal notes.
8. **Options Analytics:** Live/synthetic NSE Option Chain (PCR, Max Pain), Black-Scholes Greeks calculator, and multi-leg spread payoff diagrams.
9. **Alert Center:** Categorized alert stream (Signal, Execution, Risk, System) with unread badges, acknowledgment, and Telegram dispatches.
10. **Risk Center:** Real-time exposure gauges, daily loss tracking, drawdown meters, guardrails matrix, and emergency kill-switch.
11. **Integrations:** TradingView webhook setup with alert simulator, DhanHQ broker connection status, and Supabase SQL migration manager.
12. **Settings & Audit:** Trader profile, risk limit sliders, notification preferences, and immutable system audit trail.

---

## 5. Live Execution Safety Gate

Live execution is **disabled by default (`PAPER_TRADING_ONLY=true`)**. Real orders cannot be routed to exchange merely by providing API keys or toggling a UI switch.

Enabling live execution requires:
1. Completion of historical out-of-sample backtesting and a minimum 30-day paper trading validation period.
2. Verified broker account permissions and static-IP compliance on DhanHQ.
3. Explicit server-side configuration in `.env`:
   ```env
   PAPER_TRADING_ONLY=false
   ENABLE_LIVE_EXECUTION_DANGEROUS=true
   LIVE_EXECUTION_APPROVAL_TOKEN="your_compliance_signed_token"
   ```
4. All activations are logged to the immutable audit trail with actor, timestamp, and source IP.

Refer to [`docs/live_activation_checklist.md`](docs/live_activation_checklist.md) for full compliance instructions.

---

## 6. Project Architecture

```
algotrade-ai/
├── app/
│   ├── config.py                 # Pydantic typed configuration & safety gate
│   ├── models.py                 # Domain dataclasses & schemas
│   ├── main.py                   # FastAPI REST API & webhook listener
│   ├── risk.py                   # Central Risk Authority & guardrails
│   ├── ensemble.py               # Regime detection & ensemble consensus
│   ├── backtest.py               # Event-driven backtester & Indian tax model
│   ├── paper.py                  # Simulated paper broker & state persistence
│   ├── strategies/               # 11+ Strategy implementations
│   ├── options/                  # Greeks suite & option chains
│   ├── integrations/             # DhanHQ and TradingView adapters
│   ├── alerts/                   # Central notification dispatcher
│   ├── database/                 # Supabase & SQLite repository
│   └── ui/                       # Streamlit Workstation
│       ├── streamlit_app.py      # Multi-page application entry point
│       ├── components.py         # Theming & Plotly charts
│       └── pages/                # 12 Workstation pages
├── sql/
│   └── migrations/               # Versioned PostgreSQL migrations with RLS
├── tests/                        # 44 Automated test suites
├── docs/                         # Comprehensive architecture & guides
└── pyproject.toml                # Pinned dependencies
```
