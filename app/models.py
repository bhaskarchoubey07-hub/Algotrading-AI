from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

Direction = Literal["long", "short", "flat"]


@dataclass(frozen=True)
class StrategySignal:
    strategy_id: str
    strategy_version: str
    symbol: str
    timeframe: str
    timestamp: str
    direction: Direction
    score: float
    reason: str
    suggested_stop: float | None = None
    suggested_target: float | None = None
    regime: str = "any"

    def to_dict(self) -> dict:
        return asdict(self)


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_LIQUIDITY = "low_liquidity"
    UNCERTAIN = "uncertain"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LOSS_MARKET = "stop_loss_market"


class OrderStatus(str, Enum):
    PENDING = "pending"
    SIMULATED = "SIMULATED"
    ACCEPTED = "accepted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TradingSegment(str, Enum):
    INDEX = "INDEX"
    EQUITY_CASH = "EQUITY_CASH"
    EQUITY_FUTURES = "EQUITY_FUTURES"
    INDEX_FUTURES = "INDEX_FUTURES"
    INDEX_OPTIONS = "INDEX_OPTIONS"
    EQUITY_OPTIONS = "EQUITY_OPTIONS"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertCategory(str, Enum):
    SIGNAL = "signal"
    EXECUTION = "execution"
    RISK = "risk"
    SYSTEM = "system"


@dataclass
class AlertMessage:
    category: AlertCategory
    severity: AlertSeverity
    title: str
    message: str
    alert_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["category"] = self.category.value
        d["severity"] = self.severity.value
        return d


@dataclass
class Position:
    symbol: str
    segment: TradingSegment
    side: OrderSide
    quantity: int
    entry_price: float
    current_price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    strategy_id: str = "manual"
    notes: str = ""
    opened_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def update_price(self, price: float) -> None:
        self.current_price = price
        if self.side == OrderSide.BUY:
            self.unrealized_pnl = (self.current_price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - self.current_price) * self.quantity
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["segment"] = self.segment.value
        d["side"] = self.side.value
        return d


@dataclass
class RiskEvent:
    event_type: str
    severity: AlertSeverity
    message: str
    event_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


@dataclass
class EnsembleDecision:
    direction: Direction
    long_votes: int
    short_votes: int
    strategy_count: int
    decision: str
    regime: str
    confidence_score: float
    estimated_edge_bps: float
    trade_proposal: dict[str, Any] | None
    rationale: str
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
