from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from typing import Any
from uuid import uuid4
from app.models import OrderSide, OrderStatus, OrderType, Position, TradingSegment
from app.backtest import calculate_indian_market_charges


@dataclass
class PaperOrder:
    order_id: str
    symbol: str
    side: str
    quantity: int
    status: str
    created_at: str
    order_type: str = "MARKET"
    price: float = 0.0
    fill_price: float = 0.0
    filled_quantity: int = 0
    filled_at: str = ""
    stop_loss: float | None = None
    take_profit: float | None = None
    fees: float = 0.0
    segment: str = "EQUITY_CASH"
    strategy_id: str = "manual"
    note: str = "Simulated only; no broker request sent."

    def to_dict(self) -> dict:
        return asdict(self)


class PaperBroker:
    """Full-featured paper trading engine with realistic fills, portfolio margin and persistent state."""

    def __init__(self, initial_cash: float = 1_000_000.0, state_file: str = "paper_trading_state.json") -> None:
        self.initial_cash = initial_cash
        self.cash_balance = initial_cash
        self.realized_pnl = 0.0
        self.orders: dict[str, PaperOrder] = {}
        self.positions: dict[str, Position] = {}
        self.trades: list[dict[str, Any]] = []
        self.state_file = state_file
        self.load_state()

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float = 0.0,
        order_type: str = "MARKET",
        stop_loss: float | None = None,
        take_profit: float | None = None,
        segment: str = "EQUITY_CASH",
        strategy_id: str = "manual",
    ) -> PaperOrder:
        """Create and simulate fill for paper order."""
        side_clean = side.lower().strip()
        if side_clean not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")
        if quantity <= 0:
            raise ValueError("quantity must be positive")

        order_id = str(uuid4())
        sym_clean = symbol.upper().strip()
        now_ts = datetime.now(timezone.utc).isoformat()

        # If price is 0, estimate from existing position or default 100
        ref_price = price if price > 0 else (self.positions[sym_clean].current_price if sym_clean in self.positions else 500.0)

        # Realistic simulated slippage: 0.03% on market orders
        slippage = ref_price * 0.0003 if order_type.upper() == "MARKET" else 0.0
        fill_price = round(ref_price + slippage if side_clean == "buy" else ref_price - slippage, 2)

        # Calculate Indian regulatory charges
        turnover = fill_price * quantity
        fees = calculate_indian_market_charges(turnover if side_clean == "buy" else 0, turnover if side_clean == "sell" else 0)

        order = PaperOrder(
            order_id=order_id,
            symbol=sym_clean,
            side=side_clean,
            quantity=quantity,
            status="SIMULATED",
            created_at=now_ts,
            order_type=order_type.upper(),
            price=round(ref_price, 2),
            fill_price=fill_price,
            filled_quantity=quantity,
            filled_at=now_ts,
            stop_loss=stop_loss,
            take_profit=take_profit,
            fees=fees,
            segment=segment,
            strategy_id=strategy_id,
            note="Simulated only; no broker request sent.",
        )
        self.orders[order_id] = order

        # Update position and cash
        self._apply_fill(order)
        self.save_state()
        return order

    def _apply_fill(self, order: PaperOrder) -> None:
        sym = order.symbol
        qty = order.quantity
        price = order.fill_price
        side = order.side
        fees = order.fees

        self.cash_balance -= fees

        if sym not in self.positions:
            if side == "buy":
                cost = price * qty
                self.cash_balance -= cost
                self.positions[sym] = Position(
                    symbol=sym,
                    segment=TradingSegment(order.segment) if order.segment in TradingSegment.__members__ else TradingSegment.EQUITY_CASH,
                    side=OrderSide.BUY,
                    quantity=qty,
                    entry_price=price,
                    current_price=price,
                    stop_loss=order.stop_loss,
                    take_profit=order.take_profit,
                    strategy_id=order.strategy_id,
                )
            else:
                # Short entry
                self.cash_balance += price * qty
                self.positions[sym] = Position(
                    symbol=sym,
                    segment=TradingSegment(order.segment) if order.segment in TradingSegment.__members__ else TradingSegment.EQUITY_CASH,
                    side=OrderSide.SELL,
                    quantity=qty,
                    entry_price=price,
                    current_price=price,
                    stop_loss=order.stop_loss,
                    take_profit=order.take_profit,
                    strategy_id=order.strategy_id,
                )
        else:
            pos = self.positions[sym]
            if (pos.side == OrderSide.BUY and side == "buy") or (pos.side == OrderSide.SELL and side == "sell"):
                # Add to position (weighted average price)
                new_qty = pos.quantity + qty
                pos.entry_price = round(((pos.entry_price * pos.quantity) + (price * qty)) / new_qty, 2)
                pos.quantity = new_qty
                if side == "buy":
                    self.cash_balance -= price * qty
                else:
                    self.cash_balance += price * qty
            else:
                # Opposite side: reduce or square off
                closed_qty = min(pos.quantity, qty)
                if pos.side == OrderSide.BUY:
                    pnl = (price - pos.entry_price) * closed_qty
                    self.cash_balance += (price * closed_qty)
                else:
                    pnl = (pos.entry_price - price) * closed_qty
                    self.cash_balance -= (price * closed_qty)

                self.realized_pnl += pnl
                pos.quantity -= closed_qty
                self.trades.append({
                    "symbol": sym,
                    "closed_quantity": closed_qty,
                    "entry_price": pos.entry_price,
                    "exit_price": price,
                    "pnl": round(pnl, 2),
                    "fees": fees,
                    "closed_at": datetime.now(timezone.utc).isoformat(),
                })

                if pos.quantity == 0:
                    del self.positions[sym]

    def update_market_price(self, symbol: str, current_price: float) -> list[str]:
        """Update mark-to-market prices and evaluate automated stops."""
        triggered = []
        sym = symbol.upper().strip()
        if sym in self.positions:
            pos = self.positions[sym]
            pos.update_price(current_price)

            # Automated stop loss execution
            if pos.stop_loss:
                if (pos.side == OrderSide.BUY and current_price <= pos.stop_loss) or (pos.side == OrderSide.SELL and current_price >= pos.stop_loss):
                    self.close_position(sym, current_price, reason="AUTOMATED_STOP_LOSS")
                    triggered.append(f"{sym} STOP_LOSS executed at ₹{current_price}")

            # Automated take profit execution
            if pos.take_profit and sym in self.positions:
                if (pos.side == OrderSide.BUY and current_price >= pos.take_profit) or (pos.side == OrderSide.SELL and current_price <= pos.take_profit):
                    self.close_position(sym, current_price, reason="AUTOMATED_TAKE_PROFIT")
                    triggered.append(f"{sym} TAKE_PROFIT executed at ₹{current_price}")

        return triggered

    def close_position(self, symbol: str, exit_price: float | None = None, reason: str = "MANUAL_CLOSE") -> dict[str, Any] | None:
        sym = symbol.upper().strip()
        if sym not in self.positions:
            return None

        pos = self.positions[sym]
        price = exit_price or pos.current_price
        side = "sell" if pos.side == OrderSide.BUY else "buy"
        order = self.place_order(sym, side, pos.quantity, price=price, order_type="MARKET", strategy_id=f"close_{reason.lower()}")
        return order.to_dict()

    def list_orders(self) -> list[dict]:
        return [asdict(order) for order in self.orders.values()]

    def list_positions(self) -> list[dict]:
        return [p.to_dict() for p in self.positions.values()]

    def get_portfolio_summary(self) -> dict[str, Any]:
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        invested = sum(p.entry_price * p.quantity for p in self.positions.values())
        total_equity = self.cash_balance + invested + unrealized

        return {
            "total_equity": round(total_equity, 2),
            "cash_balance": round(self.cash_balance, 2),
            "invested_margin": round(invested, 2),
            "unrealized_pnl": round(unrealized, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "total_pnl": round(self.realized_pnl + unrealized, 2),
            "open_positions_count": len(self.positions),
            "total_orders_count": len(self.orders),
            "day_return_pct": round(((total_equity - self.initial_cash) / self.initial_cash) * 100.0, 2),
        }

    def save_state(self) -> None:
        try:
            state = {
                "initial_cash": self.initial_cash,
                "cash_balance": self.cash_balance,
                "realized_pnl": self.realized_pnl,
                "orders": [asdict(o) for o in self.orders.values()],
                "positions": [p.to_dict() for p in self.positions.values()],
                "trades": self.trades,
            }
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def load_state(self) -> None:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                self.initial_cash = state.get("initial_cash", 1_000_000.0)
                self.cash_balance = state.get("cash_balance", 1_000_000.0)
                self.realized_pnl = state.get("realized_pnl", 0.0)
                self.trades = state.get("trades", [])
                for o_dict in state.get("orders", []):
                    o = PaperOrder(**o_dict)
                    self.orders[o.order_id] = o
                for p_dict in state.get("positions", []):
                    p = Position(
                        symbol=p_dict["symbol"],
                        segment=TradingSegment(p_dict["segment"]),
                        side=OrderSide(p_dict["side"]),
                        quantity=p_dict["quantity"],
                        entry_price=p_dict["entry_price"],
                        current_price=p_dict["current_price"],
                        stop_loss=p_dict.get("stop_loss"),
                        take_profit=p_dict.get("take_profit"),
                        realized_pnl=p_dict.get("realized_pnl", 0.0),
                        unrealized_pnl=p_dict.get("unrealized_pnl", 0.0),
                        strategy_id=p_dict.get("strategy_id", "manual"),
                        notes=p_dict.get("notes", ""),
                    )
                    self.positions[p.symbol] = p
            except Exception:
                pass


paper_broker = PaperBroker()
