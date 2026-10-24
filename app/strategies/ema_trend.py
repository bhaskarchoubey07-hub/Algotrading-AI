import pandas as pd
from app.models import StrategySignal
from .base import BaseStrategy


class EmaTrendStrategy(BaseStrategy):
    strategy_id = "ema_trend"
    version = "0.1.0"
    description = "EMA 12/26 trend filter; educational baseline, not investment advice."

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        data = frame.sort_values("timestamp").copy()
        if len(data) < 30:
            direction, score, reason = "flat", 0.0, "Need at least 30 bars for warm-up."
        else:
            fast = data.close.ewm(span=12, adjust=False).mean().iloc[-1]
            slow = data.close.ewm(span=26, adjust=False).mean().iloc[-1]
            direction = "long" if fast > slow else "short" if fast < slow else "flat"
            score = float(min(abs(fast - slow) / max(float(data.close.iloc[-1]), 1e-9) * 100, 1.0))
            reason = f"EMA12={fast:.4f}; EMA26={slow:.4f}; direction={direction}."
        return StrategySignal(self.strategy_id, self.version, symbol, timeframe, str(data.timestamp.iloc[-1]), direction, score, reason)
