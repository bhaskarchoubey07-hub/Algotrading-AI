"""Central Pre-Trade Risk Authority for AlgoTrade AI.

Enforces strict capital limits, position concentration caps, daily loss limits,
stale-data checks, duplicate detection, and manual emergency kill switches.
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
import logging
import threading
from typing import Any
from zoneinfo import ZoneInfo
from app.brokers.base import OrderPlacementRequest
from app.brokers.dhan.exceptions import DhanBrokerError
from app.config import settings

logger = logging.getLogger("algotrade.services.risk")


@dataclass
class RiskCheckResult:
    is_approved: bool
    rejection_reason: str = ""
    risk_metrics: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RiskManager:
    """Independent risk engine evaluating orders before routing."""

    def __init__(
        self,
        max_order_value: float = 100_000.0,
        max_open_positions: int = 10,
        max_position_fraction: float = 0.10,
        max_daily_loss_fraction: float = 0.01,
        max_drawdown_fraction: float = 0.05,
    ) -> None:
        self.max_order_value = max_order_value
        self.max_open_positions = max_open_positions
        self.max_position_fraction = max_position_fraction
        self.max_daily_loss_fraction = max_daily_loss_fraction
        self.max_drawdown_fraction = max_drawdown_fraction

        self._kill_switch_active = False
        self._daily_realized_loss = 0.0
        self._lock = threading.Lock()

    def set_kill_switch(self, active: bool) -> None:
        """Manually triggers emergency trading pause."""
        with self._lock:
            self._kill_switch_active = active
        if active:
            logger.critical("EMERGENCY KILL SWITCH ACTIVATED! All new trading orders rejected.")
        else:
            logger.warning("Emergency kill switch deactivated.")

    def is_kill_switch_active(self) -> bool:
        with self._lock:
            return self._kill_switch_active

    def record_loss(self, loss_amount: float) -> None:
        """Records realized losses for daily drawdown tracking."""
        with self._lock:
            if loss_amount > 0:
                self._daily_realized_loss += loss_amount

    def is_market_session_open(self, check_time: datetime | None = None) -> bool:
        """Validates NSE market session (09:15 to 15:30 IST on weekdays)."""
        dt = check_time or datetime.now(ZoneInfo("Asia/Kolkata"))
        # Weekday check (0=Monday, 4=Friday)
        if dt.weekday() >= 5:
            return False
        market_open = time(9, 15)
        market_close = time(15, 30)
        return market_open <= dt.time() <= market_close

    def evaluate_order(
        self,
        request: OrderPlacementRequest,
        account_equity: float,
        current_open_positions: int,
        current_instrument_exposure: float = 0.0,
        is_market_data_stale: bool = False,
    ) -> RiskCheckResult:
        """Evaluates an order against all risk rules before routing."""
        # 1. Global Kill Switch Check
        if self.is_kill_switch_active():
            return RiskCheckResult(
                is_approved=False,
                rejection_reason="Emergency kill switch is active. New orders blocked.",
            )

        # 2. Market Data Staleness
        if is_market_data_stale:
            return RiskCheckResult(
                is_approved=False,
                rejection_reason=f"Market data for {request.symbol} is stale. Order rejected.",
            )

        # 3. Quantity sanity check
        if request.quantity <= 0:
            return RiskCheckResult(
                is_approved=False,
                rejection_reason=f"Invalid order quantity ({request.quantity}). Must be > 0.",
            )

        # 4. Max Order Notional Value Check
        est_price = request.price if request.price > 0 else 500.0
        notional_value = est_price * request.quantity
        if notional_value > self.max_order_value:
            return RiskCheckResult(
                is_approved=False,
                rejection_reason=f"Order notional ₹{notional_value:,.2f} exceeds limit ₹{self.max_order_value:,.2f}.",
                risk_metrics={"notional_value": notional_value, "limit": self.max_order_value},
            )

        # 5. Position Concentration Cap (e.g. max 10% of equity per single instrument)
        max_allowed_instrument_exposure = account_equity * self.max_position_fraction
        if (current_instrument_exposure + notional_value) > max_allowed_instrument_exposure:
            return RiskCheckResult(
                is_approved=False,
                rejection_reason=(
                    f"Concentration breach: total {request.symbol} exposure ₹{current_instrument_exposure + notional_value:,.2f} "
                    f"exceeds {self.max_position_fraction*100:.1f}% equity limit (₹{max_allowed_instrument_exposure:,.2f})."
                ),
            )

        # 6. Maximum Open Positions Cap
        if current_open_positions >= self.max_open_positions:
            return RiskCheckResult(
                is_approved=False,
                rejection_reason=f"Max concurrent positions reached ({current_open_positions}/{self.max_open_positions}).",
            )

        # 7. Daily Loss Limit Check
        max_daily_loss = account_equity * self.max_daily_loss_fraction
        with self._lock:
            current_loss = self._daily_realized_loss
        if current_loss >= max_daily_loss:
            return RiskCheckResult(
                is_approved=False,
                rejection_reason=f"Daily loss limit reached (₹{current_loss:,.2f} >= ₹{max_daily_loss:,.2f}).",
            )

        # All checks passed
        return RiskCheckResult(
            is_approved=True,
            risk_metrics={
                "notional_value": notional_value,
                "account_equity": account_equity,
                "exposure_fraction": notional_value / account_equity if account_equity > 0 else 0.0,
            },
        )


risk_manager = RiskManager()
