from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo
from app.models import AlertSeverity, OrderSide, RiskEvent, TradingSegment

IST = ZoneInfo("Asia/Kolkata")

# NSE trading hours: 09:15 to 15:30 IST
NSE_MARKET_OPEN = time(9, 15)
NSE_MARKET_CLOSE = time(15, 30)

# Major NSE Market Holidays for reference (can be extended via config)
NSE_HOLIDAYS = {
    "2026-01-26",  # Republic Day
    "2026-03-03",  # Holi
    "2026-04-14",  # Dr. Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-08-15",  # Independence Day
    "2026-10-02",  # Gandhi Jayanti
    "2026-10-20",  # Dussehra
    "2026-11-08",  # Diwali Laxmi Pujan
    "2026-12-25",  # Christmas
}


@dataclass(frozen=True)
class RiskConfig:
    risk_fraction: float = 0.0025
    max_position_value_fraction: float = 0.10
    max_daily_loss_fraction: float = 0.01
    max_drawdown_fraction: float = 0.05
    max_open_positions: int = 10
    tick_size: float = 0.05
    enforce_market_hours: bool = False  # False in backtest/dev, True in production live gate
    margin_requirement_index_futures: float = 0.15  # 15% SPAN+Exposure margin for index/equity futures


def calculate_quantity(equity: float, entry: float, stop: float, config: RiskConfig = RiskConfig()) -> int:
    """Risk-based quantity for cash equities; excludes gaps, fees and market impact."""
    if equity <= 0 or entry <= 0 or stop <= 0:
        raise ValueError("Equity, entry and stop must be positive")
    per_share_risk = abs(entry - stop)
    if per_share_risk == 0:
        raise ValueError("Entry and stop cannot be equal")
    risk_budget = equity * config.risk_fraction
    risk_qty = int(risk_budget // per_share_risk)
    exposure_qty = int((equity * config.max_position_value_fraction) // entry)
    return max(0, min(risk_qty, exposure_qty))


class RiskAuthority:
    """Central risk authority enforcing financial constraints, market hours, and safety kill switches."""

    def __init__(self, config: RiskConfig = RiskConfig(), initial_equity: float = 1_000_000.0) -> None:
        self.config = config
        self.initial_equity = initial_equity
        self.peak_equity = initial_equity
        self.daily_start_equity = initial_equity
        self.current_equity = initial_equity
        self.kill_switch_active = False
        self.circuit_breaker_tripped = False
        self.events: list[RiskEvent] = []
        self._last_order_timestamps: list[float] = []

    def sync_equity_with_broker(self, equity: float) -> None:
        """Synchronize current equity with broker portfolio value."""
        if equity > 0:
            self.current_equity = equity
            self.peak_equity = max(self.peak_equity, equity)

    def log_event(self, event_type: str, severity: AlertSeverity, message: str, details: dict[str, Any] | None = None) -> RiskEvent:
        event = RiskEvent(
            event_type=event_type,
            severity=severity,
            message=message,
            details=details or {},
        )
        self.events.append(event)
        return event

    def trip_kill_switch(self, reason: str = "Manual emergency stop") -> None:
        self.kill_switch_active = True
        self.log_event("KILL_SWITCH_TRIPPED", AlertSeverity.CRITICAL, f"Emergency kill switch activated: {reason}")

    def reset_kill_switch(self) -> None:
        self.kill_switch_active = False
        self.circuit_breaker_tripped = False
        self.log_event("KILL_SWITCH_RESET", AlertSeverity.WARNING, "Emergency kill switch has been reset.")

    def update_equity(self, equity: float) -> None:
        self.current_equity = equity
        if equity > self.peak_equity:
            self.peak_equity = equity

        # Check peak-to-trough drawdown
        drawdown_pct = (self.peak_equity - equity) / self.peak_equity if self.peak_equity > 0 else 0.0
        if drawdown_pct >= self.config.max_drawdown_fraction:
            self.circuit_breaker_tripped = True
            self.kill_switch_active = True
            self.log_event(
                "DRAWDOWN_CIRCUIT_BREAKER",
                AlertSeverity.CRITICAL,
                f"Peak-to-trough drawdown limit breached: {drawdown_pct:.2%}. Circuit breaker tripped.",
                {"drawdown_pct": drawdown_pct, "peak_equity": self.peak_equity, "current_equity": equity},
            )

        # Check daily loss limit
        daily_loss_pct = (self.daily_start_equity - equity) / self.daily_start_equity if self.daily_start_equity > 0 else 0.0
        if daily_loss_pct >= self.config.max_daily_loss_fraction:
            self.circuit_breaker_tripped = True
            self.kill_switch_active = True
            self.log_event(
                "DAILY_LOSS_BREACH",
                AlertSeverity.CRITICAL,
                f"Daily loss limit breached: {daily_loss_pct:.2%}. Trading halted for the day.",
                {"daily_loss_pct": daily_loss_pct, "daily_start_equity": self.daily_start_equity},
            )

    def is_market_open(self, now: datetime | None = None) -> tuple[bool, str]:
        """Check if Indian market is open (NSE regular equity/f&o session)."""
        dt = now.astimezone(IST) if now else datetime.now(IST)
        date_str = dt.strftime("%Y-%m-%d")
        
        # Weekend check
        if dt.weekday() >= 5:
            return False, f"Market closed: Weekend ({dt.strftime('%A')})"
        
        # Holiday check
        if date_str in NSE_HOLIDAYS:
            return False, f"Market closed: NSE Holiday ({date_str})"
            
        current_time = dt.time()
        if current_time < NSE_MARKET_OPEN:
            return False, f"Market pre-open: session begins at 09:15 IST (current: {current_time.strftime('%H:%M:%S')})"
        if current_time > NSE_MARKET_CLOSE:
            return False, f"Market closed: session ended at 15:30 IST (current: {current_time.strftime('%H:%M:%S')})"
            
        return True, "Market is OPEN"

    def validate_tick_size(self, price: float) -> bool:
        """Validate price adheres to NSE tick size (typically 0.05)."""
        if price <= 0:
            return False
        remainder = round((price / self.config.tick_size) % 1, 4)
        return remainder in (0.0, 1.0)

    def validate_order(
        self,
        symbol: str,
        side: OrderSide | str,
        quantity: int,
        price: float,
        current_positions_count: int,
        segment: TradingSegment | str = TradingSegment.EQUITY_CASH,
        lot_size: int = 1,
    ) -> tuple[bool, str]:
        """Full pre-trade risk inspection."""
        if self.kill_switch_active:
            return False, "Order rejected: Emergency kill-switch / circuit-breaker is ACTIVE."

        if quantity <= 0:
            return False, "Order rejected: Quantity must be strictly positive."

        if price <= 0:
            return False, "Order rejected: Price must be positive."

        if quantity % lot_size != 0:
            return False, f"Order rejected: Quantity {quantity} is not a multiple of lot size {lot_size}."

        if current_positions_count >= self.config.max_open_positions:
            return False, f"Order rejected: Maximum open positions ({self.config.max_open_positions}) reached."

        # Maximum position value constraint with derivative/index margin calculation
        order_value = price * quantity
        max_position_val = self.current_equity * self.config.max_position_value_fraction

        # Check if instrument is an index / derivative margin instrument
        is_derivative = (
            segment in {TradingSegment.INDEX, TradingSegment.INDEX_FUTURES, TradingSegment.EQUITY_FUTURES, "INDEX", "INDEX_FUTURES", "EQUITY_FUTURES"}
            or symbol.endswith("_FUT")
            or symbol in {"NIFTY 50", "BANKNIFTY", "FINNIFTY"}
        )
        margin_rate = self.config.margin_requirement_index_futures if is_derivative else 1.0
        effective_value = order_value * margin_rate

        if effective_value > max_position_val:
            if is_derivative:
                return False, f"Order rejected: Order required margin ₹{effective_value:,.2f} (notional ₹{order_value:,.2f}) exceeds max allowed ₹{max_position_val:,.2f}."
            return False, f"Order rejected: Order notional value ₹{order_value:,.2f} exceeds max allowed ₹{max_position_val:,.2f}."

        if self.config.enforce_market_hours:
            open_ok, msg = self.is_market_open()
            if not open_ok:
                return False, f"Order rejected: {msg}"

        return True, "Order passed all risk authority checks."

    def get_risk_snapshot(self) -> dict[str, Any]:
        return {
            "kill_switch_active": self.kill_switch_active,
            "circuit_breaker_tripped": self.circuit_breaker_tripped,
            "current_equity": self.current_equity,
            "peak_equity": self.peak_equity,
            "daily_start_equity": self.daily_start_equity,
            "drawdown_pct": (self.peak_equity - self.current_equity) / self.peak_equity if self.peak_equity > 0 else 0.0,
            "daily_loss_pct": (self.daily_start_equity - self.current_equity) / self.daily_start_equity if self.daily_start_equity > 0 else 0.0,
            "max_drawdown_limit": self.config.max_drawdown_fraction,
            "max_daily_loss_limit": self.config.max_daily_loss_fraction,
            "max_open_positions": self.config.max_open_positions,
            "events_count": len(self.events),
        }


risk_authority = RiskAuthority()
