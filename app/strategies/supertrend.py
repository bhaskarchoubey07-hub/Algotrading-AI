import numpy as np
import pandas as pd
from app.models import StrategySignal
from app.strategies.base import BaseStrategy


class SupertrendStrategy(BaseStrategy):
    strategy_id = "supertrend"
    version = "1.0.0"
    description = "Supertrend ATR trend-following strategy with dynamic volatility trailing stops."
    category = "trend"
    supported_regimes = ["trending_up", "trending_down"]

    def __init__(self, period: int = 10, multiplier: float = 3.0) -> None:
        self.period = period
        self.multiplier = multiplier
        self.parameters = {"period": period, "multiplier": multiplier}

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        if len(frame) < self.period + 5:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame.timestamp.iloc[-1]),
                direction="flat",
                score=0.0,
                reason=f"Insufficient bars for warmup (need at least {self.period + 5})",
            )

        df = frame.copy().reset_index(drop=True)
        high = df["high"]
        low = df["low"]
        close = df["close"]

        # True Range calculation
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=self.period).mean()

        hl2 = (high + low) / 2.0
        basic_upper = hl2 + (self.multiplier * atr)
        basic_lower = hl2 - (self.multiplier * atr)

        final_upper = basic_upper.copy()
        final_lower = basic_lower.copy()

        trend = np.zeros(len(df))

        for i in range(self.period, len(df)):
            # Final upper band
            if basic_upper.iloc[i] < final_upper.iloc[i - 1] or close.iloc[i - 1] > final_upper.iloc[i - 1]:
                final_upper.iloc[i] = basic_upper.iloc[i]
            else:
                final_upper.iloc[i] = final_upper.iloc[i - 1]

            # Final lower band
            if basic_lower.iloc[i] > final_lower.iloc[i - 1] or close.iloc[i - 1] < final_lower.iloc[i - 1]:
                final_lower.iloc[i] = basic_lower.iloc[i]
            else:
                final_lower.iloc[i] = final_lower.iloc[i - 1]

            # Supertrend direction
            if trend[i - 1] == 1 and close.iloc[i] < final_lower.iloc[i]:
                trend[i] = -1
            elif trend[i - 1] == -1 and close.iloc[i] > final_upper.iloc[i]:
                trend[i] = 1
            else:
                trend[i] = trend[i - 1] if trend[i - 1] != 0 else (1 if close.iloc[i] > hl2.iloc[i] else -1)

        curr_trend = trend[-1]
        curr_close = float(close.iloc[-1])
        curr_atr = float(atr.iloc[-1])

        if curr_trend == 1:
            direction = "long"
            score = 0.85
            stop = float(final_lower.iloc[-1])
            target = curr_close + 2.0 * curr_atr
            reason = f"Supertrend bullish (close {curr_close:.2f} > band {stop:.2f})"
        elif curr_trend == -1:
            direction = "short"
            score = 0.85
            stop = float(final_upper.iloc[-1])
            target = curr_close - 2.0 * curr_atr
            reason = f"Supertrend bearish (close {curr_close:.2f} < band {stop:.2f})"
        else:
            direction = "flat"
            score = 0.0
            stop = None
            target = None
            reason = "Supertrend neutral"

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_version=self.version,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=str(frame.timestamp.iloc[-1]),
            direction=direction,
            score=score,
            reason=reason,
            suggested_stop=round(stop, 2) if stop else None,
            suggested_target=round(target, 2) if target else None,
            regime="trending",
        )
