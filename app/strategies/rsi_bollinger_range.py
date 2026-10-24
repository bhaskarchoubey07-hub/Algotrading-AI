"""Strategy: RSI & Bollinger Range Mean Reversion
Regime: RANGE_BOUND / LOW_VOLATILITY
Combines oversold/overbought oscillator signals (RSI < 30 or > 70) with outer
Bollinger Band (20, 2σ) piercing, targeted exclusively for sideways/consolidating regimes.
"""

from typing import Any
import pandas as pd
from app.indicators import calculate_bollinger_bands, calculate_rsi
from app.models import StrategySignal
from .base import BaseStrategy


class RsiBollingerRangeStrategy(BaseStrategy):
    strategy_id = "rsi_bollinger_range"
    version = "1.0.0"
    description = "Counter-trend mean reversion designed specifically for range-bound sideways markets."
    category = "mean_reversion"
    supported_regimes = ["range_bound", "low_volatility"]

    def __init__(self, rsi_period: int = 14, bb_period: int = 20, oversold: float = 30.0, overbought: float = 70.0) -> None:
        self.rsi_period = rsi_period
        self.bb_period = bb_period
        self.oversold = oversold
        self.overbought = overbought
        self.parameters = {
            "rsi_period": rsi_period,
            "bb_period": bb_period,
            "oversold": oversold,
            "overbought": overbought,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": "RSI + Bollinger Range Reversion",
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "regimes": self.supported_regimes,
            "warm_up_bars": max(self.rsi_period, self.bb_period) + 5,
            "supported_segments": ["EQUITY_CASH", "INDEX"],
            "timeframes": ["5m", "15m", "1h", "1d"],
            "parameters": self.parameters,
            "is_promoted": True,
        }

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        min_bars = max(self.rsi_period, self.bb_period) + 5
        if len(frame) < min_bars:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="flat",
                score=0.0,
                reason="Insufficient warm-up data for RSI and Bollinger calculation.",
                regime="range_bound",
            )

        c = frame["close"]
        l = frame["low"]
        h = frame["high"]

        rsi = calculate_rsi(c, period=self.rsi_period)
        bb = calculate_bollinger_bands(c, period=self.bb_period, num_std=2.0)

        curr_close = float(c.iloc[-1])
        curr_low = float(l.iloc[-1])
        curr_high = float(h.iloc[-1])
        curr_rsi = float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
        bb_upper = float(bb.upper.iloc[-1]) if not pd.isna(bb.upper.iloc[-1]) else curr_close * 1.02
        bb_lower = float(bb.lower.iloc[-1]) if not pd.isna(bb.lower.iloc[-1]) else curr_close * 0.98
        bb_mid = float(bb.middle.iloc[-1]) if not pd.isna(bb.middle.iloc[-1]) else curr_close

        # Long Mean Reversion: Low pierces lower Bollinger Band AND RSI is oversold
        if curr_low <= bb_lower and curr_rsi <= self.oversold:
            conf = min(0.88, 0.60 + (self.oversold - curr_rsi) / 30.0 * 0.3)
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="long",
                score=round(conf, 2),
                reason=f"Oversold range bounce: RSI {curr_rsi:.1f} and price pierced lower band ₹{bb_lower:,.2f}.",
                suggested_stop=round(bb_lower * 0.99, 2),
                suggested_target=round(bb_mid, 2),
                regime="range_bound",
            )

        # Short Mean Reversion: High pierces upper Bollinger Band AND RSI is overbought
        if curr_high >= bb_upper and curr_rsi >= self.overbought:
            conf = min(0.88, 0.60 + (curr_rsi - self.overbought) / 30.0 * 0.3)
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="short",
                score=round(conf, 2),
                reason=f"Overbought range reversal: RSI {curr_rsi:.1f} and price pierced upper band ₹{bb_upper:,.2f}.",
                suggested_stop=round(bb_upper * 1.01, 2),
                suggested_target=round(bb_mid, 2),
                regime="range_bound",
            )

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_version=self.version,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=str(frame["timestamp"].iloc[-1]),
            direction="flat",
            score=0.2,
            reason="Price is within normal statistical distribution envelopes.",
            regime="range_bound",
        )
