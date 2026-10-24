import pandas as pd
from app.models import StrategySignal
from app.strategies.base import BaseStrategy


class SwingPullbackStrategy(BaseStrategy):
    strategy_id = "swing_pullback"
    version = "1.0.0"
    description = "Multi-day trend pullback swing strategy targeting dip entries in established trends."
    category = "swing"
    supported_regimes = ["trending_up", "trending_down"]

    def __init__(self, trend_ema: int = 50, trigger_ema: int = 20, pullback_pct: float = 1.0) -> None:
        self.trend_ema = trend_ema
        self.trigger_ema = trigger_ema
        self.pullback_pct = pullback_pct
        self.parameters = {
            "trend_ema": trend_ema,
            "trigger_ema": trigger_ema,
            "pullback_pct": pullback_pct,
        }

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        min_bars = max(self.trend_ema, self.trigger_ema) + 5
        if len(frame) < min_bars:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame.timestamp.iloc[-1]),
                direction="flat",
                score=0.0,
                reason=f"Insufficient bars for warmup (need at least {min_bars})",
            )

        df = frame.copy().reset_index(drop=True)
        close = df["close"]
        low = df["low"]
        high = df["high"]

        trend = close.ewm(span=self.trend_ema, adjust=False).mean()
        trigger = close.ewm(span=self.trigger_ema, adjust=False).mean()

        curr_close = float(close.iloc[-1])
        curr_low = float(low.iloc[-1])
        curr_high = float(high.iloc[-1])
        curr_trend = float(trend.iloc[-1])
        curr_trigger = float(trigger.iloc[-1])

        # Uptrend: trend line rising and price above long-term trend
        is_uptrend = curr_trigger > curr_trend and curr_close > curr_trend
        is_downtrend = curr_trigger < curr_trend and curr_close < curr_trend

        # Pullback test near 20 EMA
        if is_uptrend and curr_low <= curr_trigger * (1.0 + self.pullback_pct / 100.0) and curr_close >= curr_trigger:
            direction = "long"
            score = 0.80
            stop = curr_trend * 0.98
            target = curr_close * 1.08
            reason = f"Bullish swing pullback: dip held 20-EMA ({curr_trigger:.2f}) above rising 50-EMA ({curr_trend:.2f})"
        elif is_downtrend and curr_high >= curr_trigger * (1.0 - self.pullback_pct / 100.0) and curr_close <= curr_trigger:
            direction = "short"
            score = 0.80
            stop = curr_trend * 1.02
            target = curr_close * 0.92
            reason = f"Bearish swing pullback: rally rejected at 20-EMA ({curr_trigger:.2f}) below falling 50-EMA ({curr_trend:.2f})"
        else:
            direction = "flat"
            score = 0.0
            stop, target = None, None
            reason = "No clean swing pullback setup detected"

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
            regime="swing",
        )
