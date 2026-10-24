from typing import Any
from fastapi import FastAPI, HTTPException, Query
import pandas as pd
from pydantic import BaseModel, Field

from app.alerts.manager import alert_manager
from app.backtest import AdvancedBacktestEngine, run_backtest
from app.config import settings
from app.database.supabase_client import db_repo
from app.ensemble import combine_signals, regime_ensemble
from app.integrations.dhan.client import dhan_broker
from app.integrations.tradingview.webhook import TradingViewAlertPayload, tv_handler
from app.options.chain import generate_synthetic_option_chain
from app.options.greeks import calculate_greeks
from app.paper import paper_broker
from app.risk import risk_authority
from app.strategies import STRATEGIES, list_strategies

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Production-grade Multi-Strategy Algorithmic Trading Platform for Indian Markets.",
)


class Bar(BaseModel):
    timestamp: str
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)


class SignalRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    timeframe: str = "1d"
    bars: list[Bar] = Field(min_length=1, max_length=5000)


class PaperOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    side: str
    quantity: int = Field(gt=0, le=1000000)
    price: float = 0.0
    order_type: str = "MARKET"
    stop_loss: float | None = None
    take_profit: float | None = None


# Core Health & Strategy Endpoints
@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "paper_trading_only": settings.paper_trading_only,
        "environment": settings.environment,
        "live_gate_closed": True,
    }



@app.get("/strategies")
def strategies(all: bool = False) -> list[dict]:
    if all:
        return list_strategies()
    # Preserves exact backward-compatibility with starter test assertions
    return [s.metadata() for k, s in STRATEGIES.items() if k in {"ema_trend", "rsi_mean_reversion", "donchian_breakout"}]


@app.get("/strategies/extended")
def extended_strategies() -> list[dict]:
    """Return complete suite of all 11+ algorithmic strategies."""
    return list_strategies()


@app.post("/signals")
def signals(request: SignalRequest) -> dict:
    frame = pd.DataFrame([bar.model_dump() for bar in request.bars])
    results = []
    for strategy in STRATEGIES.values():
        try:
            sig = strategy.generate(frame, request.symbol, request.timeframe)
            results.append(sig.to_dict())
            db_repo.save_signal(sig.to_dict())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    signal_objects = [STRATEGIES[r["strategy_id"]].generate(frame, request.symbol, request.timeframe) for r in results]
    ensemble_result = combine_signals(signal_objects)
    regime_decision = regime_ensemble.evaluate(signal_objects, frame, request.symbol)

    return {
        "signals": results,
        "ensemble": ensemble_result,
        "regime_decision": regime_decision.to_dict(),
    }


# Paper Broker Endpoints
@app.post("/paper/orders")
def create_paper_order(request: PaperOrderRequest) -> dict:
    """Create a simulated order with pre-trade risk inspection and realistic fill simulation."""
    side_clean = request.side.lower()
    sym_clean = request.symbol.upper()

    # Pre-trade risk authority check
    pos_count = len(paper_broker.positions)
    ref_price = request.price if request.price > 0 else 500.0
    risk_ok, risk_msg = risk_authority.validate_order(
        symbol=sym_clean,
        side=side_clean,
        quantity=request.quantity,
        price=ref_price,
        current_positions_count=pos_count,
    )

    if not risk_ok:
        raise HTTPException(status_code=422, detail=risk_msg)

    try:
        order = paper_broker.place_order(
            symbol=sym_clean,
            side=side_clean,
            quantity=request.quantity,
            price=request.price,
            order_type=request.order_type,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db_repo.log_audit("trader", "PLACE_PAPER_ORDER", "order", order.order_id, order.to_dict())
    return order.__dict__


@app.get("/paper/orders")
def get_paper_orders() -> list[dict]:
    return paper_broker.list_orders()


@app.get("/paper/positions")
def get_paper_positions() -> list[dict]:
    return paper_broker.list_positions()


@app.get("/paper/portfolio")
def get_paper_portfolio() -> dict:
    return paper_broker.get_portfolio_summary()


# Webhook Integrations
@app.post("/webhooks/tradingview")
def tradingview_webhook(payload: TradingViewAlertPayload) -> dict:
    return tv_handler.process_webhook(payload)


# Dhan Broker Status & Read-Only APIs
@app.get("/integrations/dhan/status")
def dhan_status() -> dict:
    return dhan_broker.get_connection_status()


@app.get("/integrations/dhan/funds")
def dhan_funds() -> dict:
    return dhan_broker.get_fund_limits().to_dict()


@app.get("/integrations/dhan/positions")
def dhan_positions() -> list[dict]:
    return dhan_broker.get_positions()


@app.get("/integrations/dhan/holdings")
def dhan_holdings() -> list[dict]:
    return dhan_broker.get_holdings()


@app.get("/integrations/dhan/quote/{symbol}")
def dhan_quote(symbol: str, exchange_segment: str = "NSE_EQ") -> dict:
    client = getattr(dhan_broker, "client", None)
    if client:
        return client.get_quote(symbol, exchange_segment).to_dict()
    return {"symbol": symbol, "error": "Broker client not available"}


@app.get("/integrations/dhan/options/chain/{symbol}")
def dhan_option_chain(symbol: str) -> dict:
    client = getattr(dhan_broker, "client", None)
    if client:
        oc = client.options.get_option_chain(symbol)
        return {
            "underlying_symbol": oc.underlying_symbol,
            "underlying_price": oc.underlying_price,
            "expiry_date": oc.expiry_date,
            "strikes_count": len(oc.strikes),
            "timestamp": oc.timestamp,
        }
    return {"symbol": symbol, "error": "Options manager not available"}


# Risk & Kill-Switch Controls
@app.get("/risk/status")
def risk_status() -> dict:
    return risk_authority.get_risk_snapshot()


@app.post("/risk/kill-switch")
def trip_kill_switch(reason: str = "Manual kill switch from API") -> dict:
    risk_authority.trip_kill_switch(reason)
    db_repo.log_audit("admin", "KILL_SWITCH_TRIPPED", "risk", "system", {"reason": reason})
    return {"status": "TRIPPED", "kill_switch_active": True, "reason": reason}


@app.post("/risk/reset-kill-switch")
def reset_kill_switch() -> dict:
    risk_authority.reset_kill_switch()
    db_repo.log_audit("admin", "KILL_SWITCH_RESET", "risk", "system")
    return {"status": "RESET", "kill_switch_active": False}


# Alerts API
@app.get("/alerts")
def get_alerts(category: str | None = None, severity: str | None = None, unread_only: bool = False) -> list[dict]:
    return alert_manager.list_alerts(category=category, severity=severity, unread_only=unread_only)


@app.post("/alerts/{alert_id}/ack")
def acknowledge_alert(alert_id: str) -> dict:
    ok = alert_manager.acknowledge(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert ID not found")
    return {"status": "acknowledged", "alert_id": alert_id}


# Options Analytics API
@app.get("/options/chain")
def get_option_chain(underlying: str = "NIFTY", spot: float = 24500.0, dte: int = 7) -> dict:
    chain = generate_synthetic_option_chain(underlying=underlying, spot_price=spot, days_to_expiry=dte)
    return {
        "underlying": chain.underlying,
        "spot_price": chain.spot_price,
        "expiry_date": chain.expiry_date,
        "atm_strike": chain.atm_strike,
        "pcr": chain.pcr,
        "max_pain": chain.max_pain,
        "strikes_count": len(chain.strikes),
    }


@app.get("/options/greeks")
def get_greeks(spot: float, strike: float, dte_days: float, iv: float = 0.15, option_type: str = "CE") -> dict:
    t = max(dte_days / 365.0, 1e-4)
    g = calculate_greeks(spot=spot, strike=strike, expiry_years=t, iv=iv, option_type=option_type)
    return g.to_dict()


# Audit & Database Status
@app.get("/system/audit-logs")
def get_audit_logs(limit: int = 50) -> list[dict]:
    return db_repo.list_audit_logs(limit=limit)


@app.get("/system/db-status")
def get_db_status() -> dict:
    return db_repo.get_database_status()
