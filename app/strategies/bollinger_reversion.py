import pandas as pd
from app.models import StrategySignal
from app.strategies.base import BaseStrategy


class BollingerReversionStrategy(BaseStrategy):
    strategy_id = "bollinger_reversion"
    version = "1.0.0"
    description = "Bollinger Bands mean-reversion with statistical Z-score thresholding."
    category = "mean_reversion"
    supported_regimes = ["range_bound", "low_liquidity"]

    def __init__(self, period: int = 20, num_std: float = 2.0, z_entry: float = 2.0) -> None:
        self.period = period
        self.num_std = num_std
        self.z_entry = z_entry
        self.parameters = {
            "period": period,
            "num_std": num_std,
            "z_entry": z_entry,
        }

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
        close = df["close"]

        sma = close.rolling(window=self.period).mean()
        std = close.rolling(window=self.period).std()
        upper = sma + (self.num_std * std)
        lower = sma - (self.num_std * std)

        curr_close = float(close.iloc[-1])
        curr_sma = float(sma.iloc[-1])
        curr_std = float(std.iloc[-1]) if float(std.iloc[-1]) > 0 else 1.0
        curr_upper = float(upper.iloc[-1])
        curr_lower = float(lower.iloc[-1])

        z_score = (curr_close - curr_sma) / curr_std

        if z_score <= -self.z_entry or curr_close < curr_lower:
            direction = "long"
            score = min(0.90, 0.60 + min(abs(z_score) / 5.0, 0.30))
            stop = curr_close - 2.0 * curr_std
            target = curr_sma
            reason = f"Oversold reversion: Z-score {z_score:.2f} <= -{self.z_entry} (below lower band {curr_lower:.2f})"
        elif z_score >= self.z_entry or curr_close > curr_upper:
            direction = "short"
            score = min(0.90, 0.60 + min(z_score / 5.0, 0.30))
            stop = curr_close + 2.0 * curr_std
            target = curr_sma
            reason = f"Overbought reversion: Z-score +{z_score:.2f} >= +{self.z_entry} (above upper band {curr_upper:.2f})"
        else:
            direction = "flat"
            score = 0.0
            stop, target = None, None
            reason = f"Within normal bands (Z-score {z_score:.2f})"

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
            regime="mean_reversion",
        )
