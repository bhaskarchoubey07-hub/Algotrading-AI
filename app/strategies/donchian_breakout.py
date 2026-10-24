import pandas as pd
from app.models import StrategySignal
from .base import BaseStrategy


class DonchianBreakoutStrategy(BaseStrategy):
    strategy_id = "donchian_breakout"
    version = "0.1.0"
    description = "20-bar Donchian close breakout baseline; signal uses completed bars only."

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        data = frame.sort_values("timestamp").copy()
        if len(data) < 22:
            direction, score, reason = "flat", 0.0, "Need at least 22 bars for breakout comparison."
        else:
            prior = data.iloc[-21:-1]
            close = float(data.close.iloc[-1])
            high = float(prior.high.max())
            low = float(prior.low.min())
            if close > high:
                direction, score, reason = "long", min((close - high) / high, 1.0), f"Close {close:.4f} broke above prior 20-bar high {high:.4f}."
            elif close < low:
                direction, score, reason = "short", min((low - close) / low, 1.0), f"Close {close:.4f} broke below prior 20-bar low {low:.4f}."
            else:
                direction, score, reason = "flat", 0.0, "No 20-bar breakout."
        return StrategySignal(self.strategy_id, self.version, symbol, timeframe, str(data.timestamp.iloc[-1]), direction, float(score), reason)
