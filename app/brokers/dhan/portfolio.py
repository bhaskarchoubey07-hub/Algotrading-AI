"""DhanHQ Portfolio, Margin, and Positions Manager."""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any
from app.brokers.base import BrokerFundLimit, BrokerHolding, BrokerPosition
from app.brokers.dhan.normalizers import (
    normalize_fund_limits,
    normalize_holding,
    normalize_position,
)

logger = logging.getLogger("algotrade.dhan.portfolio")


@dataclass
class MarginCalculationResult:
    total_margin_required: float
    span_margin: float = 0.0
    exposure_margin: float = 0.0
    available_margin: float = 0.0
    sufficient_funds: bool = True
    shortfall: float = 0.0


class DhanPortfolioManager:
    """Manages account fund limits, holdings, positions, and margin calculations."""

    def __init__(self, dhan_client: Any = None) -> None:
        self._client = dhan_client

    def set_client(self, dhan_client: Any) -> None:
        self._client = dhan_client

    def get_fund_limits(self) -> BrokerFundLimit:
        """Retrieves fund limits from DhanHQ or returns sandbox default."""
        if self._client and hasattr(self._client, "get_fund_limits"):
            try:
                res = self._client.get_fund_limits()
                if isinstance(res, dict) and "data" in res:
                    return normalize_fund_limits(res["data"])
                elif isinstance(res, dict):
                    return normalize_fund_limits(res)
            except Exception as exc:
                logger.error(f"Dhan get_fund_limits error: {exc}. Using sandbox funds.")

        # Sandbox default values
        return BrokerFundLimit(
            available_cash=850_000.0,
            collateral_amount=150_000.0,
            margin_utilized=75_000.0,
            net_equity=925_000.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def get_positions(self) -> list[BrokerPosition]:
        """Retrieves open positions from DhanHQ or returns sandbox positions."""
        if self._client and hasattr(self._client, "get_positions"):
            try:
                res = self._client.get_positions()
                raw_list = res.get("data", res) if isinstance(res, dict) else res
                if isinstance(raw_list, list):
                    return [normalize_position(p) for p in raw_list]
            except Exception as exc:
                logger.error(f"Dhan get_positions error: {exc}. Using sandbox positions.")

        # Sandbox position
        return [
            BrokerPosition(
                symbol="RELIANCE",
                exchange_segment="NSE_EQ",
                position_type="LONG",
                net_quantity=25,
                buy_average=2840.50,
                cost_price=2840.50,
                current_price=2845.00,
                realized_pnl=0.0,
                unrealized_pnl=112.50,
                cross_currency="INR",
            )
        ]

    def get_holdings(self) -> list[BrokerHolding]:
        """Retrieves demat holdings from DhanHQ or returns sandbox holdings."""
        if self._client and hasattr(self._client, "get_holdings"):
            try:
                res = self._client.get_holdings()
                raw_list = res.get("data", res) if isinstance(res, dict) else res
                if isinstance(raw_list, list):
                    return [normalize_holding(h) for h in raw_list]
            except Exception as exc:
                logger.error(f"Dhan get_holdings error: {exc}. Using sandbox holdings.")

        return [
            BrokerHolding(
                symbol="INFY",
                isin="INE009A01021",
                total_quantity=50,
                dp_quantity=50,
                average_cost_price=1720.00,
                current_market_price=1750.25,
                pnl=1512.50,
            )
        ]

    def calculate_margin(
        self,
        security_id: str,
        exchange_segment: str,
        transaction_type: str,
        quantity: int,
        product_type: str,
        price: float,
        trigger_price: float = 0.0,
    ) -> MarginCalculationResult:
        """Calculates margin requirement using Dhan margin calculator or internal formula."""
        if self._client and hasattr(self._client, "margin_calculator"):
            try:
                res = self._client.margin_calculator(
                    security_id=security_id,
                    exchange_segment=exchange_segment,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    product_type=product_type,
                    price=price,
                    trigger_price=trigger_price,
                )
                if isinstance(res, dict) and "data" in res:
                    m = res["data"]
                    total = float(m.get("totalMargin") or price * quantity)
                    funds = self.get_fund_limits()
                    shortfall = max(0.0, total - funds.available_cash)
                    return MarginCalculationResult(
                        total_margin_required=total,
                        span_margin=float(m.get("spanMargin") or 0.0),
                        exposure_margin=float(m.get("exposureMargin") or 0.0),
                        available_margin=funds.available_cash,
                        sufficient_funds=(shortfall == 0.0),
                        shortfall=shortfall,
                    )
            except Exception as exc:
                logger.warning(f"Dhan margin_calculator error: {exc}. Using formula estimation.")

        # Conservative estimation formula
        notional = price * quantity
        if product_type == "INTRADAY":
            total_req = notional * 0.20  # 5x leverage for intraday cash
        else:
            total_req = notional  # 100% margin for delivery CNC
        funds = self.get_fund_limits()
        shortfall = max(0.0, total_req - funds.available_cash)
        return MarginCalculationResult(
            total_margin_required=round(total_req, 2),
            span_margin=0.0,
            exposure_margin=round(total_req, 2),
            available_margin=funds.available_cash,
            sufficient_funds=(shortfall == 0.0),
            shortfall=round(shortfall, 2),
        )
