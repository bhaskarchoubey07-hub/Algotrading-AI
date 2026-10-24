# AlgoTrade AI — Architecture Documentation

## System Architecture Overview

AlgoTrade AI is an enterprise-grade multi-strategy algorithmic trading platform designed for Indian markets (NSE Cash, Futures, and Options). It combines an asynchronous FastAPI backend service with a modern Streamlit quantitative trading terminal.

```
                          ┌───────────────────────────┐
                          │   TradingView Webhook     │
                          │   (PineScript Alerts)     │
                          └─────────────┬─────────────┘
                                        │ HTTPS HMAC
                                        ▼
┌───────────────────────────┐     ┌─────────────────────────────────────────────────────────┐
│   Streamlit Dashboard     │     │                      FastAPI Service                    │
│   (12 Workstation Pages)  │◄───►│  - Endpoints: /signals, /paper/orders, /webhooks/tv     │
└─────────────┬─────────────┘     └───────────────────────────┬─────────────────────────────┘
              │                                               │
              ▼                                               ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                                   Core Domain Subsystems                                  │
│                                                                                           │
│   ┌──────────────────────────┐    ┌──────────────────────────┐    ┌───────────────────┐   │
│   │   Strategy Laboratory    │    │   Regime & Ensemble      │    │  Risk Authority   │   │
│   │   - 11+ Strategies       │───►│   - ADX/ATR Detector     │───►│  - Drawdown Halt  │   │
│   │   - Trend, Momentum,     │    │   - Conflict Resolution  │    │  - Max Daily Loss │   │
│   │     Breakout, Options, ML│    │   - Net Edge Estimation  │    │  - Market Hours   │   │
│   └──────────────────────────┘    └──────────────────────────┘    └─────────┬─────────┘   │
│                                                                             │             │
│   ┌──────────────────────────┐    ┌──────────────────────────┐              ▼             │
│   │   Backtest Laboratory    │    │  Options Analytics       │    ┌───────────────────┐   │
│   │   - Chronological Loop   │    │  - Black-Scholes Greeks  │    │   Paper Broker    │   │
│   │   - Indian STT/Charges   │    │  - Option Chain & PCR    │    │   - Spread/Slip   │   │
│   │   - Walk-Forward Valid.  │    │  - Multi-Leg Payoffs     │    │   - Auto SL / TP  │   │
│   └──────────────────────────┘    └──────────────────────────┘    └─────────┬─────────┘   │
└─────────────────────────────────────────────┬───────────────────────────────┼─────────────┘
                                              │                               │
                                              ▼                               ▼
                                ┌───────────────────────────┐   ┌───────────────────────────┐
                                │   Supabase PostgreSQL     │   │   DhanHQ Broker Adapter   │
                                │   - RLS Multi-Tenant Data │   │   - Sandbox Simulation    │
                                │   - Signals, Orders, Logs │   │   - Live Execution Gate   │
                                └───────────────────────────┘   └───────────────────────────┘
```

## Modular Layer Breakdown

1. **`app/models.py`**: Typed domain models, dataclasses, and enums representing `StrategySignal`, `EnsembleDecision`, `Position`, `PaperOrder`, `RiskEvent`, `AlertMessage`, and `OptionGreeks`.
2. **`app/risk.py`**: Central Risk Authority enforcing strict pre-trade and intraday guardrails:
   - Per-trade risk budget sizing.
   - Max single position notional (10% equity default).
   - Daily loss limit (1% default) and peak-to-trough drawdown circuit breaker (5% default).
   - NSE trading session hours (09:15 to 15:30 IST) and market holiday validation.
   - Emergency kill switch for instant trading halt.
3. **`app/strategies/`**: Independent, modular strategy plugins with standard metadata and normalized outputs. Emits proposals; never executes directly.
4. **`app/ensemble.py`**: Regime classification using ADX, ATR%, moving average slopes, and Bollinger bandwidth. Routes eligible strategies, resolves long/short conflicts, and calculates net edge after roundtrip transaction charges.
5. **`app/backtest.py`**: Event-driven chronological backtest engine without future leakage, modeling Indian statutory transaction taxes (STT, exchange turnover, SEBI, GST, stamp duty), stop loss/take profit triggers, walk-forward splits, and metrics (Sharpe, Sortino, CAGR, drawdown).
6. **`app/paper.py`**: Simulated paper execution broker with bid-ask spread and slippage modeling, automated stop-loss management, position closing, and persistent state storage.
7. **`app/options/`**: Black-Scholes European pricing, complete Greeks calculation (Delta, Gamma, Theta, Vega, Rho), implied volatility solver, and multi-leg spread payoff diagrams.
8. **`app/integrations/`**:
   - `tradingview/`: HMAC-secured webhook listener with timestamp drift protection and event-id replay defense.
   - `dhan/`: Official DhanHQ OpenAPI v2 client with sandbox simulation and strict server-side live execution gate.
9. **`app/alerts/`**: Multi-channel alert dispatching (in-app, Telegram, email) with deduplication and acknowledgment.
10. **`app/database/`**: Dual-mode database repository supporting Supabase PostgREST cloud storage and automatic local SQLite fallback.
