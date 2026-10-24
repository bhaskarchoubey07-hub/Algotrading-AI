"""Payload Normalizers and Redaction Utilities for DhanHQ responses."""

from datetime import datetime, timezone
import re
from typing import Any
from app.brokers.base import (
    BrokerFundLimit,
    BrokerHolding,
    BrokerOrder,
    BrokerPosition,
    BrokerQuote,
    OrderStatus,
)

SENSITIVE_KEYS = {
    "access_token",
    "token",
    "client_id",
    "clientid",
    "password",
    "pin",
    "totp",
    "secret",
    "authorization",
    "pan",
    "bank_account",
    "account_number",
}


def redact_sensitive_data(data: Any) -> Any:
    """Recursively redacts API keys, tokens, and sensitive PII from dicts and lists."""
    if isinstance(data, dict):
        cleaned: dict[str, Any] = {}
        for k, v in data.items():
            key_lower = k.lower().replace("-", "_")
            if any(s in key_lower for s in SENSITIVE_KEYS):
                cleaned[k] = "[REDACTED]"
            elif isinstance(v, (dict, list)):
                cleaned[k] = redact_sensitive_data(v)
            else:
                cleaned[k] = v
        return cleaned
    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]
    return data


def normalize_fund_limits(data: dict[str, Any]) -> BrokerFundLimit:
    """Normalizes raw DhanHQ /fundlimit response."""
    return BrokerFundLimit(
        available_cash=float(data.get("availabelBalance") or data.get("available_cash") or 0.0),
        collateral_amount=float(data.get("collateralAmount") or data.get("collateral_amount") or 0.0),
        margin_utilized=float(data.get("utilisedAmount") or data.get("margin_utilized") or 0.0),
        net_equity=float(data.get("netEquity") or data.get("net_equity") or 0.0),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def normalize_position(data: dict[str, Any]) -> BrokerPosition:
    """Normalizes raw DhanHQ /positions response item."""
    buy_avg = float(data.get("buyAvg") or data.get("buy_average") or 0.0)
    cost_price = float(data.get("costPrice") or data.get("cost_price") or buy_avg)
    return BrokerPosition(
        symbol=str(data.get("tradingSymbol") or data.get("symbol") or "UNKNOWN"),
        exchange_segment=str(data.get("exchangeSegment") or data.get("exchange_segment") or "NSE_EQ"),
        position_type=str(data.get("positionType") or data.get("position_type") or "LONG").upper(),
        net_quantity=int(data.get("netQty") or data.get("net_quantity") or 0),
        buy_average=buy_avg,
        cost_price=cost_price,
        current_price=float(data.get("costPrice") or data.get("current_price") or cost_price),
        realized_pnl=float(data.get("realizedProfit") or data.get("realized_pnl") or 0.0),
        unrealized_pnl=float(data.get("unrealizedProfit") or data.get("unrealized_pnl") or 0.0),
        cross_currency=str(data.get("crossCurrency") or "INR"),
    )


def normalize_holding(data: dict[str, Any]) -> BrokerHolding:
    """Normalizes raw DhanHQ /holdings response item."""
    avg_cost = float(data.get("avgCostPrice") or data.get("average_cost_price") or 0.0)
    total_qty = int(data.get("totalQty") or data.get("total_quantity") or 0)
    dp_qty = int(data.get("dpQty") or data.get("dp_quantity") or total_qty)
    cmp_val = float(data.get("costPrice") or data.get("current_market_price") or avg_cost)
    return BrokerHolding(
        symbol=str(data.get("tradingSymbol") or data.get("symbol") or "UNKNOWN"),
        isin=str(data.get("isin") or ""),
        total_quantity=total_qty,
        dp_quantity=dp_qty,
        average_cost_price=avg_cost,
        current_market_price=cmp_val,
        pnl=(cmp_val - avg_cost) * total_qty,
    )


def map_dhan_order_status(status_str: str) -> OrderStatus:
    """Maps Dhan order status string to internal OrderStatus enum."""
    s = (status_str or "").upper()
    if "TRANSIT" in s or "SANDBOX" in s:
        return OrderStatus.TRANSIT_SANDBOX
    elif s in {"TRADED", "FILLED", "EXECUTED", "COMPLETE"}:
        return OrderStatus.FILLED
    elif s in {"CANCELLED", "CANCELED"}:
        return OrderStatus.CANCELLED
    elif s in {"REJECTED"}:
        return OrderStatus.REJECTED
    elif s in {"PENDING", "OPEN"}:
        return OrderStatus.PENDING
    elif s in {"PART_TRADED", "PARTIALLY_FILLED"}:
        return OrderStatus.PARTIALLY_FILLED
    elif s in {"EXPIRED"}:
        return OrderStatus.EXPIRED
    return OrderStatus.SUBMITTED


def normalize_order(data: dict[str, Any]) -> BrokerOrder:
    """Normalizes raw DhanHQ order item into BrokerOrder."""
    raw_status = str(data.get("orderStatus") or data.get("order_status") or "PENDING")
    order_id = str(data.get("orderId") or data.get("order_id") or "")
    corr_id = str(data.get("correlationId") or data.get("correlation_id") or order_id)
    return BrokerOrder(
        order_id=order_id,
        correlation_id=corr_id,
        symbol=str(data.get("tradingSymbol") or data.get("symbol") or "UNKNOWN"),
        security_id=str(data.get("securityId") or data.get("security_id") or ""),
        exchange_segment=str(data.get("exchangeSegment") or data.get("exchange_segment") or "NSE_EQ"),
        transaction_type=str(data.get("transactionType") or data.get("transaction_type") or "BUY").upper(),
        order_type=str(data.get("orderType") or data.get("order_type") or "MARKET").upper(),
        product_type=str(data.get("productType") or data.get("product_type") or "CNC").upper(),
        quantity=int(data.get("quantity") or 0),
        price=float(data.get("price") or 0.0),
        trigger_price=float(data.get("triggerPrice") or data.get("trigger_price") or 0.0),
        order_status=map_dhan_order_status(raw_status),
        exchange_order_id=str(data.get("exchangeOrderId") or data.get("exchange_order_id") or ""),
        created_at=str(data.get("createTime") or data.get("created_at") or datetime.now(timezone.utc).isoformat()),
        filled_quantity=int(data.get("filledQty") or data.get("filled_quantity") or 0),
        filled_price=float(data.get("averageTradedPrice") or data.get("filled_price") or 0.0),
        filled_at=data.get("exchangeTime") or data.get("filled_at"),
        message=str(data.get("message") or ""),
        is_live=bool(data.get("is_live", False)),
    )


def normalize_quote(data: dict[str, Any], symbol: str = "UNKNOWN", security_id: str = "") -> BrokerQuote:
    """Normalizes raw DhanHQ /marketfeed/quote response."""
    depth_data = data.get("depth", {})
    return BrokerQuote(
        symbol=symbol,
        security_id=security_id or str(data.get("securityId", "")),
        exchange_segment=str(data.get("exchangeSegment", "NSE_EQ")),
        last_price=float(data.get("last_price") or data.get("LTP") or 0.0),
        open_price=float(data.get("open") or 0.0),
        high_price=float(data.get("high") or 0.0),
        low_price=float(data.get("low") or 0.0),
        close_price=float(data.get("close") or 0.0),
        volume=int(data.get("volume") or 0),
        timestamp=str(data.get("timestamp") or datetime.now(timezone.utc).isoformat()),
        is_stale=False,
        depth=depth_data,
    )
