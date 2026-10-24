# DhanHQ OpenAPI v2 Integration Guide for AlgoTrade AI

## 1. Overview and Architecture

AlgoTrade AI integrates the official [DhanHQ Python SDK (dhanhq >= 2.3.0)](https://github.com/dhan-oss/DhanHQ-py) via a modular, production-grade broker abstraction layer. The integration provides real-time market data, scrip master resolution, quotes, order state machines, portfolio and margin monitoring, options chains with Greeks, WebSocket streaming, and strict pre-trade risk controls.

### Architectural Subsystem (`app/brokers/dhan/`)

```
app/
├── brokers/
│   ├── base.py                   # Unified BaseBroker abstract interface and domain dataclasses
│   └── dhan/
│       ├── __init__.py           # Package exports
│       ├── client.py             # DhanClient (SDK factory) & DhanHQBrokerAdapter (backward compatible)
│       ├── auth.py               # DhanAuthManager (token validation, zero-leak redaction)
│       ├── exceptions.py         # Domain-specific exceptions (DhanBrokerError, StaleDataError, etc.)
│       ├── normalizers.py        # Response payload normalizers and PII/secret redaction
│       ├── instruments.py        # DhanInstrumentManager (scrip master CDN sync & symbol resolver)
│       ├── market_data.py        # DhanMarketDataManager (quotes, historical daily, intraday, staleness)
│       ├── orders.py             # DhanOrderManager (state machine, idempotency, correlation IDs)
│       ├── portfolio.py          # DhanPortfolioManager (margins, funds, positions, holdings)
│       ├── options.py            # DhanOptionsManager (option chains, expiry lists, Black-Scholes Greeks)
│       └── streaming.py          # DhanStreamingManager (WebSocket MarketFeed, exponential backoff)
├── services/
│   ├── risk_manager.py           # Pre-trade risk enforcement and emergency kill switch
│   ├── execution_engine.py       # Unified router: BACKTEST, PAPER, LIVE_GATED
│   └── paper_trading.py          # Persistent paper trading engine facade
```

---

## 2. API Capability Matrix

| API Capability | DhanHQ SDK Method | Status in AlgoTrade AI | Notes |
|---|---|---|---|
| **Authentication** | `DhanContext(client_id, token)` | **Implemented & Tested** | Zero-leak token masking in UI & logs |
| **Fund Limits & Margins** | `dhanhq.get_fund_limits()` | **Implemented & Tested** | Normalized to `BrokerFundLimit` |
| **Positions Book** | `dhanhq.get_positions()` | **Implemented & Tested** | Live or simulated sandbox positions |
| **Demat Holdings** | `dhanhq.get_holdings()` | **Implemented & Tested** | Normalized to `BrokerHolding` |
| **Margin Calculator** | `dhanhq.margin_calculator()` | **Implemented & Tested** | Supports CNC (100%) & INTRADAY (20%) |
| **Live Market Quotes** | `dhanhq.quote_data()` | **Implemented & Tested** | 5s TTL cache + Staleness validation |
| **Historical Daily Data** | `dhanhq.historical_daily_data()` | **Implemented & Tested** | Chronological pandas DataFrame |
| **Intraday Minute Data** | `dhanhq.intraday_minute_data()` | **Implemented & Tested** | Configurable intervals (1m, 5m, 15m) |
| **Scrip Master CDN** | `Security.COMPACT_CSV_URL` | **Implemented & Tested** | Automated download & in-memory resolver |
| **Option Chain Ladder** | `dhanhq.option_chain()` | **Implemented & Tested** | Calculates Delta, Gamma, Theta, Vega |
| **Contract Expiries** | `dhanhq.expiry_list()` | **Implemented & Tested** | Resolves weekly & monthly derivative expiries |
| **Order Placement** | `dhanhq.place_order()` | **Gated in Sandbox** | Returns `TRANSIT_SANDBOX` order |
| **Order Modification** | `dhanhq.modify_order()` | **Implemented & Tested** | Guarded by order state machine |
| **Order Cancellation** | `dhanhq.cancel_order()` | **Implemented & Tested** | Transitions status to `CANCELLED` |
| **MarketFeed WebSocket** | `marketfeed.MarketFeed` | **Implemented & Tested** | Exponential backoff with jitter |
| **OrderUpdate WebSocket**| `orderupdate.OrderUpdate` | **Implemented & Tested** | Async connection handler |
| **Live Exchange Execution**| Exchange Gateway | **Gated / Disabled** | Requires compliance sign-off & live flag |

---

## 3. Authentication & Credential Setup

Dhan uses a **Personal Access Token** mechanism that does not require scraping or automated browser logins.

### How to Obtain DhanHQ Credentials:
1. Log in to [Dhan Web Portal](https://web.dhan.co/).
2. Click **My Profile** -> **DhanHQ Trading APIs**.
3. Under **Access Token**, generate your 30-day API Access Token.
4. Note down your numeric **Client ID** (e.g., `1000000001`).
5. Open your local `.env` file and set:
   ```env
   DHAN_CLIENT_ID=1000000001
   DHAN_ACCESS_TOKEN=eyJhbGciOiJIUzI1NiIsIn...
   DHAN_ENV=sandbox # or live
   ```

> [!CAUTION]
> Never commit `.env` or paste access tokens into code, issues, or chats. Tokens are automatically redacted in logs and diagnostic outputs.

---

## 4. Multi-Barrier Safety & Risk Gates

All orders submitted through the platform pass through the **Pre-Trade Risk Authority** (`app.services.risk_manager.RiskManager`):

1. **Global Emergency Kill Switch**: If tripped, all incoming orders are immediately blocked.
2. **Market Data Staleness Check**: Quotes older than 60 seconds trigger `DhanStaleDataError` and reject trade proposals.
3. **Idempotency Protection**: Orders with identical parameters submitted within 5 seconds are flagged as duplicates and rejected.
4. **Order Notional Value Cap**: Default ₹1,00,000 per order limit.
5. **Position Concentration Cap**: Maximum 10% of portfolio equity in a single instrument.
6. **Concurrent Positions Cap**: Maximum 10 concurrent active positions.
7. **Daily Realized Drawdown Limit**: 1.0% maximum daily portfolio loss circuit breaker.

---

## 5. Execution Modes & Live-Trading Checklist

The platform operates in three explicit modes:

- **BACKTEST**: Point-in-time chronological simulation using historical bars.
- **PAPER (Default)**: Durable simulated execution modeling slippage, brokerage, and portfolio margin.
- **LIVE_GATED**: Live broker routing mode.

### Live-Trading Transition Checklist:
1. Valid Dhan client ID and unexpired access token verified.
2. Market data feed latency verified < 1,000 ms.
3. Risk parameters (order limits, max positions, drawdown circuit breakers) calibrated.
4. Scrip master updated and security IDs verified against target instruments.
5. User provides explicit written confirmation.
