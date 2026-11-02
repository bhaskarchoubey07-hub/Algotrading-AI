from abc import ABC, abstractmethod
from typing import Any
import pandas as pd
from app.models import StrategySignal

REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}


class BaseStrategy(ABC):
    strategy_id = "base"
    version = "0.1.0"
    description = "Base strategy"
    category = "general"
    parameters: dict[str, Any] = {}
    entry_exit_logic: str = "Standard algorithmic rules"
    supported_segments: list[str] = ["EQUITY_CASH", "INDEX", "INDEX_FUTURES"]
    supported_timeframes: list[str] = ["5m", "15m", "1h", "1d"]
    required_data: list[str] = ["OHLCV bars (min 30 bars)"]
    regime_eligibility: list[str] = ["any"]
    validation_status: str = "active"

    def set_parameters(self, params: dict[str, Any]) -> None:
        """Configures strategy parameters dynamically."""
        for k, v in params.items():
            if hasattr(self, k):
                setattr(self, k, v)
        self.parameters.update(params)

    def metadata(self) -> dict[str, Any]:
        """Provides complete quantitative specification for Strategy Registry & Laboratory."""
        return {
            "strategy_id": self.strategy_id,
            "version": self.version,
            "description": self.description,
            "category": getattr(self, "category", "general"),
            "parameters": getattr(self, "parameters", {}),
            "entry_exit_logic": getattr(self, "entry_exit_logic", "Standard algorithmic rules"),
            "supported_segments": getattr(self, "supported_segments", ["EQUITY_CASH", "INDEX"]),
            "supported_timeframes": getattr(self, "supported_timeframes", ["5m", "15m", "1h", "1d"]),
            "required_data": getattr(self, "required_data", ["OHLCV bars"]),
            "supported_regimes": getattr(self, "regime_eligibility", ["any"]),
            "regimes": getattr(self, "regime_eligibility", ["any"]),
            "validation_status": getattr(self, "validation_status", "active"),
        }

    def validate(self, frame: pd.DataFrame) -> None:
        missing = REQUIRED_COLUMNS - set(frame.columns)
        if missing:
            raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")
        if frame.empty:
            raise ValueError("OHLCV data cannot be empty")
        if frame[list(REQUIRED_COLUMNS - {"timestamp"})].isna().any().any():
            raise ValueError("OHLCV numeric columns contain null values")
        if (frame["close"] <= 0).any():
            raise ValueError("Close prices must be positive")

    @abstractmethod
    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        """Generate a signal from historical bars. Signal is not an order."""
