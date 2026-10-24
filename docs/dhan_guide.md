# DhanHQ Broker Integration Guide

AlgoTrade AI integrates with the official **DhanHQ OpenAPI v2** for Indian equity cash, futures, and options markets.

## Setup & Credentials

1. Register for API access via Dhan web portal (**Dhan Web -> Profile -> DhanHQ Trading APIs**).
2. Generate your **Client ID** and **Access Token**.
3. Set the following variables in your `.env` file:
   ```env
   DHAN_CLIENT_ID=your_client_id_here
   DHAN_ACCESS_TOKEN=your_jwt_access_token_here
   DHAN_ENV=sandbox   # Set to 'live' only after full qualification
   ```

## Supported Operations

- **Margin & Funds Inquiry:** Fetches available cash balance, collateral margin, and utilised margin.
- **Positions Reconciliation:** Compares local paper positions with broker demat/trading positions.
- **Holdings Inquiry:** Displays delivery holdings portfolio.
- **Order Placement & Modification:** Supports MARKET, LIMIT, STOP_LOSS orders with Day validity.

## Safety & Compliance Gate

- By default, `PAPER_TRADING_ONLY=true`. In this mode, all DhanHQ order calls are handled by the built-in sandbox simulator with zero exchange risk.
- Live order routing is permanently disabled until the server-side approval token and live flag are verified.
