# Paper Trading Guide

AlgoTrade AI features a persistent simulated broker modeling realistic execution dynamics for Indian markets.

## Key Features

1. **Realistic Transaction Costs:**
   - Automatically computes Indian statutory taxes: Brokerage (₹20/trade), STT, Exchange Turnover, SEBI charges, GST (18%), and Stamp Duty.
2. **Spread & Slippage Modeling:**
   - Market orders incorporate 0.03% (3 bps) realistic fill slippage.
3. **Automated Stop Loss & Take Profit:**
   - Active paper positions are evaluated against current market ticks. If mark-to-market drops below stop loss, the position is automatically squared off.
4. **Restart Recovery:**
   - All open positions, orders, and cash balances are serialized to `paper_trading_state.json` and mirrored in the database repository. Restarting the server preserves all simulated trading state.

## How to Start Paper Trading

1. Launch the Streamlit dashboard:
   ```bash
   streamlit run app/ui/streamlit_app.py
   ```
2. Navigate to **6. Paper Trading**.
3. Use the **Manual Order Ticket** to place sample orders.
4. Monitor active positions, mark-to-market P&L, and closed trades in **7. Portfolio & Positions**.
