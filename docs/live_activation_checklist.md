# Live Execution Activation Checklist & Compliance Gate

Live automated execution carries financial and regulatory risk. By design, AlgoTrade AI is **paper-only by default**.

## Mandatory Pre-Flight Criteria

Before enabling live execution, all of the following steps must be verified and documented:

- [ ] **1. Out-of-Sample Backtesting Validation:**
  - Backtest evaluated on out-of-sample data with positive net expectancy after transaction costs and slippage.
  - Walk-forward degradation is within acceptable thresholds (< 30%).
- [ ] **2. 30-Day Paper Trading Period:**
  - Minimum of 30 consecutive calendar days of paper trading with daily position and cash reconciliation.
- [ ] **3. Risk Limits & Circuit Breakers Tested:**
  - Emergency kill switch tested and verified in staging.
  - Drawdown circuit breaker (e.g. 5%) and daily loss limit (e.g. 1%) configured.
- [ ] **4. SEBI & Exchange Compliance:**
  - Verified applicable SEBI guidelines on algorithmic trading, API tagging, and broker algo approval.
- [ ] **5. Broker Requirements (DhanHQ):**
  - Confirmed static IP address requirement if applicable on Dhan.
  - Verified segment permissions (NSE Cash, F&O) and active API subscription.
- [ ] **6. Production Server Hardening:**
  - HTTPS / TLS 1.3 configured on reverse proxy (Nginx / Caddy).
  - Firewall blocking public access to PostgreSQL / internal ports.
  - Strong, unique secrets configured for `TRADINGVIEW_WEBHOOK_SECRET`.
- [ ] **7. Executive & Risk Officer Approval:**
  - System administrator generates a cryptographically strong `LIVE_EXECUTION_APPROVAL_TOKEN`.
  - Update `.env`:
    ```env
    PAPER_TRADING_ONLY=false
    ENABLE_LIVE_EXECUTION_DANGEROUS=true
    LIVE_EXECUTION_APPROVAL_TOKEN="your_approved_token"
    ```
  - Platform logs the authorization event with actor, timestamp, and IP in the immutable audit trail.
