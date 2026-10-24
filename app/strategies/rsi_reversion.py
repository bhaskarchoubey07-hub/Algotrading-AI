import pandas as pd
from app.models import StrategySignal
from .base import BaseStrategy


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    out = 100 - (100 / (1 + rs))
    return out.fillna(50)


class RsiMeanReversionStrategy(BaseStrategy):
    strategy_id = "rsi_mean_reversion"
    version = "0.1.0"
    description = "RSI 14 extreme-level mean-reversion baseline; disable during strong trends."

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        data = frame.sort_values("timestamp").copy()
        value = float(rsi(data.close).iloc[-1])
        if len(data) < 20:
            direction, score, reason = "flat", 0.0, "Need at least 20 bars for warm-up."
        elif value < 30:
            direction, score, reason = "long", min((30 - value) / 30, 1.0), f"RSI14={value:.2f}; oversold candidate."
        elif value > 70:
            direction, score, reason = "short", min((value - 70) / 30, 1.0), f"RSI14={value:.2f}; overbought candidate."
        else:
            direction, score, reason = "flat", 0.0, f"RSI14={value:.2f}; no extreme."
        return StrategySignal(self.strategy_id, self.version, symbol, timeframe, str(data.timestamp.iloc[-1]), direction, float(score), reason)
