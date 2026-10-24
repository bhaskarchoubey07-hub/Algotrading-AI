# TradingView Webhook & Alert Setup Guide

This guide describes how to connect TradingView alerts and Pine Script strategies to AlgoTrade AI.

## Webhook Endpoint Configuration

- **Webhook URL:** `https://your-public-server.com/webhooks/tradingview`
- **Method:** `POST`
- **Content-Type:** `application/json`

## Security Requirements

1. Set `TRADINGVIEW_WEBHOOK_SECRET` in `.env` to a long, unpredictable passphrase.
2. In your TradingView alert message body, include the `"passphrase": "your_secure_secret"` field.
3. Every alert must include a unique `"event_id"` (e.g. UUID or timestamped ID) to enable replay attack defense.
4. Timestamps must be in ISO-8601 UTC format. Webhooks with timestamp drift greater than 120 seconds are automatically rejected.

## Pine Script Alert Payload Template

Paste the following JSON format into your TradingView Alert Message field:

```json
{
  "event_id": "{{strategy.order.id}}-{{timenow}}",
  "strategy_id": "tv_ema_crossover",
  "strategy_version": "1.0.0",
  "symbol": "{{ticker}}",
  "exchange": "NSE",
  "timeframe": "{{interval}}",
  "signal_type": "entry",
  "direction": "{{strategy.order.action}}",
  "timestamp": "{{timenow}}",
  "reference_price": {{close}},
  "suggested_stop": {{plot("Stop_Loss")}},
  "suggested_target": {{plot("Target_Price")}},
  "passphrase": "your_secure_webhook_secret_here",
  "rationale": "TradingView 15-min Supertrend / EMA confirmation"
}
```

## Testing Your Webhook

You can test the webhook receiver locally without TradingView:
1. Open the Streamlit terminal page: **11. Integrations -> TradingView Webhook**.
2. Click **Simulate TradingView Alert Post**.
3. Verify the alert appears in **9. Alert Center** and updates the paper positions.
