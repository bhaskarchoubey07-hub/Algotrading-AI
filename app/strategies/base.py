from abc import ABC, abstractmethod
import pandas as pd
from app.models import StrategySignal

REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}


class BaseStrategy(ABC):
    strategy_id = "base"
    version = "0.1.0"
    description = "Base strategy"

    def metadata(self) -> dict:
        return {"strategy_id": self.strategy_id, "version": self.version, "description": self.description}

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
