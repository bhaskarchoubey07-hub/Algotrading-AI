# Security & Incident Response Guide

## Security Architecture

1. **Least-Privilege Principle:**
   - Broker API secrets (`DHAN_ACCESS_TOKEN`) and database service keys are stored strictly in server-side environment files (`.env`) with `chmod 600`.
   - Client applications and browsers never receive broker tokens or service role keys.
2. **Replay & Timestamp Defenses:**
   - Webhooks enforce unique `event_id` tracking in a 24-hour cache.
   - Timestamps older than 120 seconds or skewed into the future are dropped immediately.
3. **Fail-Closed Execution Gate:**
   - Live trading cannot be enabled via the UI alone. It requires server environment configuration and cryptographic token authorization.
   - Any unhandled exception in risk validation halts order routing and logs a critical risk alert.

## Incident Response Runbook

### Incident Type 1: Broker API Disconnect or Market Feed Timeout
1. The platform automatically trips a `SYSTEM` warning alert.
2. New order proposals are rejected with `NO_TRADE`.
3. Open positions are retained with existing broker stop-loss orders.
4. Review logs:
   ```bash
   tail -f logs/algotrade.log
   ```

### Incident Type 2: Runaway Order Loop / Abnormal Executions
1. Immediately trip the **Emergency Kill Switch** via:
   - Sidebar in Streamlit dashboard: **🚨 Emergency Halt**
   - API: `POST /risk/kill-switch`
   - Terminal:
     ```bash
     curl -X POST http://127.0.0.1:8000/risk/kill-switch
     ```
2. Check `paper_broker.list_positions()` or Dhan portal.
3. Square off open positions if risk threshold has been breached.
4. Review the immutable audit log table in `sql/migrations/002_platform_tables.sql` or **12. Settings & Audit**.
