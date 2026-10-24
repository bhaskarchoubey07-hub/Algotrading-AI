# Troubleshooting Guide

Common issues, diagnostic checks, and operational recovery solutions.

## 1. Emergency Kill Switch Tripped

**Symptom:**
- Orders fail with message `Order rejected: Emergency kill-switch / circuit-breaker is ACTIVE.`
- Streamlit displays red `KILL-SWITCH: ACTIVE` banner.

**Resolution:**
1. Navigate to **10. Risk Center** or use the sidebar button.
2. Review the **Historical Risk Events Log** to identify which limit was breached (e.g. Drawdown breach, Daily loss breach, Manual halt).
3. If market conditions have stabilized and drawdown is within tolerance, click **RESET KILL-SWITCH**.

## 2. TradingView Webhook 401 Unauthorized

**Symptom:**
- TradingView alert log shows HTTP 401 response.

**Resolution:**
1. Check `TRADINGVIEW_WEBHOOK_SECRET` in `.env`.
2. Confirm that your TradingView alert message body contains `"passphrase": "your_matching_secret"`.

## 3. Webhook 400 Stale Timestamp

**Symptom:**
- Webhook response shows: `Webhook timestamp too old or too far in future`.

**Resolution:**
1. Ensure the server system clock is NTP-synchronized.
2. In PineScript, ensure `{{timenow}}` or ISO timestamp is passed without artificial delays.

## 4. Port Conflicts

**Symptom:**
- `uvicorn` or `streamlit` fails to bind to port 8000 or 8501.

**Resolution:**
- FastAPI: `uvicorn app.main:app --port 8001`
- Streamlit: `streamlit run app/ui/streamlit_app.py --server.port 8502`
