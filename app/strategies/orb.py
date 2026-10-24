import pandas as pd
from app.models import StrategySignal
from app.strategies.base import BaseStrategy


class OpeningRangeBreakoutStrategy(BaseStrategy):
    strategy_id = "orb_breakout"
    version = "1.0.0"
    description = "Opening-Range Breakout (ORB) strategy trading beyond early session extremes."
    category = "breakout"
    supported_regimes = ["trending_up", "trending_down", "high_volatility"]

    def __init__(self, range_bars: int = 15, breakout_buffer_pct: float = 0.1) -> None:
        self.range_bars = range_bars
        self.breakout_buffer_pct = breakout_buffer_pct
        self.parameters = {
            "range_bars": range_bars,
            "breakout_buffer_pct": breakout_buffer_pct,
        }

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "15m") -> StrategySignal:
        self.validate(frame)
        if len(frame) < self.range_bars + 2:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame.timestamp.iloc[-1]),
                direction="flat",
                score=0.0,
                reason=f"Insufficient bars to form opening range (need at least {self.range_bars + 2})",
            )

        df = frame.copy().reset_index(drop=True)
        opening_window = df.iloc[:self.range_bars]
        or_high = float(opening_window["high"].max())
        or_low = float(opening_window["low"].min())
        or_range = or_high - or_low

        curr_close = float(df["close"].iloc[-1])
        curr_volume = float(df["volume"].iloc[-1])
        avg_volume = float(opening_window["volume"].mean())

        buffer = (self.breakout_buffer_pct / 100.0) * or_high

        if curr_close > (or_high + buffer):
            direction = "long"
            score = 0.82 if curr_volume > avg_volume else 0.65
            stop = or_low
            target = curr_close + or_range * 1.5
            reason = f"ORB upside breakout: close {curr_close:.2f} above range high {or_high:.2f}"
        elif curr_close < (or_low - buffer):
            direction = "short"
            score = 0.82 if curr_volume > avg_volume else 0.65
            stop = or_high
            target = curr_close - or_range * 1.5
            reason = f"ORB downside breakdown: close {curr_close:.2f} below range low {or_low:.2f}"
        else:
            direction = "flat"
            score = 0.0
            stop, target = None, None
            reason = f"Inside opening range [{or_low:.2f} - {or_high:.2f}]"

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
            regime="breakout",
        )
