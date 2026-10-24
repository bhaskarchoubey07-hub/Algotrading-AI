# AlgoTrade AI — REST API Documentation

The FastAPI service is mounted on `http://127.0.0.1:8000` with interactive Swagger docs at `/docs`.

## Core Endpoints

### 1. System Health
- **`GET /health`**
  - **Description:** Returns system status, paper trading enforcement state, and environment.
  - **Response:**
    ```json
    {
      "status": "ok",
      "paper_trading_only": true,
      "environment": "development",
      "version": "1.0.0",
      "live_gate_closed": true
    }
    ```

### 2. Strategy Registry
- **`GET /strategies?all=false`**
  - Returns starter registered strategies (maintains 100% backward compatibility).
- **`GET /strategies/extended`** or **`GET /strategies?all=true`**
  - Returns all 11+ algorithmic strategies across all families.

### 3. Signal Generation & Ensemble Evaluation
- **`POST /signals`**
  - **Body:**
    ```json
    {
      "symbol": "RELIANCE",
      "timeframe": "1d",
      "bars": [
        {"timestamp":"2025-01-01T00:00:00Z","open":2800,"high":2820,"low":2790,"close":2815,"volume":100000}
      ]
    }
    ```
  - **Response:**
    Returns list of strategy signals, majority ensemble vote, and `regime_decision` with net edge estimation.

### 4. Paper Broker Execution
- **`POST /paper/orders`**
  - **Body:**
    ```json
    {
      "symbol": "RELIANCE",
      "side": "buy",
      "quantity": 10,
      "price": 2840.0,
      "order_type": "MARKET",
      "stop_loss": 2790.0,
      "take_profit": 2950.0
    }
    ```
- **`GET /paper/orders`**: List all active and historical simulated orders.
- **`GET /paper/positions`**: List open paper positions with mark-to-market unrealized P&L.
- **`GET /paper/portfolio`**: Fetch consolidated equity, available cash, and margin summary.

### 5. Webhook Integrations
- **`POST /webhooks/tradingview`**
  - Accepts authenticated PineScript alert payloads with timestamp freshness and replay defense.

### 6. Risk Authority Controls
- **`GET /risk/status`**: Current drawdown, daily loss, and kill switch status.
- **`POST /risk/kill-switch`**: Immediately trips emergency halt on all order flow.
- **`POST /risk/reset-kill-switch`**: Resets emergency halt after review.

### 7. Options Desk
- **`GET /options/chain?underlying=NIFTY&spot=24650&dte=7`**: Returns complete option chain, strikes, open interest, PCR, and max pain strike.
- **`GET /options/greeks?spot=24500&strike=24500&dte_days=7&iv=0.15&option_type=CE`**: Calculates Black-Scholes theoretical price, Delta, Gamma, Theta, Vega, and Rho.
