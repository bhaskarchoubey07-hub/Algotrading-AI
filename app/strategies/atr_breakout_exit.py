"""Strategy: ATR Volatility Breakout with Dynamic Trailing Exits
Regime: HIGH_VOLATILITY / TRENDING
Uses Average True Range (14) to adapt stop loss distance, position sizing risk,
and multi-bar trailing volatility stops.
"""

from typing import Any
import pandas as pd
from app.indicators import calculate_atr
from app.models import StrategySignal
from .base import BaseStrategy


class AtrBreakoutExitStrategy(BaseStrategy):
    strategy_id = "atr_breakout_exit"
    version = "1.0.0"
    description = "Volatility-scaled channel breakout with ATR-adjusted stop distance."
    category = "breakout"
    supported_regimes = ["high_volatility", "trending_up", "trending_down"]

    def __init__(self, atr_period: int = 14, atr_mult: float = 2.0, lookback: int = 20) -> None:
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.lookback = lookback
        self.parameters = {
            "atr_period": atr_period,
            "atr_mult": atr_mult,
            "lookback": lookback,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": "ATR Dynamic Volatility Breakout & Exit",
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "regimes": self.supported_regimes,
            "warm_up_bars": max(self.atr_period, self.lookback) + 5,
            "supported_segments": ["EQUITY_CASH", "EQUITY_FUTURES", "INDEX"],
            "timeframes": ["15m", "1h", "1d"],
            "parameters": self.parameters,
            "is_promoted": True,
        }

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        min_bars = max(self.atr_period, self.lookback) + 5
        if len(frame) < min_bars:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="flat",
                score=0.0,
                reason="Insufficient bars for ATR calculation.",
                regime="uncertain",
            )

        c = frame["close"]
        h = frame["high"]
        l = frame["low"]

        atr = calculate_atr(h, l, c, period=self.atr_period, smoothing="wilder")

        curr_close = float(c.iloc[-1])
        curr_atr = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else curr_close * 0.015
        roll_high = float(h.iloc[-self.lookback - 1 : -1].max())
        roll_low = float(l.iloc[-self.lookback - 1 : -1].min())

        # Bullish: Breakout above lookback high, stop placed at 2x ATR
        if curr_close > roll_high:
            stop_dist = curr_atr * self.atr_mult
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="long",
                score=0.82,
                reason=f"Breakout above {self.lookback}-bar high (₹{roll_high:,.2f}) with dynamic ATR stop ₹{stop_dist:,.2f}.",
                suggested_stop=round(curr_close - stop_dist, 2),
                suggested_target=round(curr_close + (stop_dist * 2.0), 2),
                regime="high_volatility",
            )

        # Bearish: Breakdown below lookback low, stop placed at 2x ATR
        if curr_close < roll_low:
            stop_dist = curr_atr * self.atr_mult
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="short",
                score=0.82,
                reason=f"Breakdown below {self.lookback}-bar low (₹{roll_low:,.2f}) with dynamic ATR stop ₹{stop_dist:,.2f}.",
                suggested_stop=round(curr_close + stop_dist, 2),
                suggested_target=round(curr_close - (stop_dist * 2.0), 2),
                regime="high_volatility",
            )

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_version=self.version,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=str(frame["timestamp"].iloc[-1]),
            direction="flat",
            score=0.3,
            reason="Price remains within ATR volatility envelope.",
            regime="range_bound",
        )
