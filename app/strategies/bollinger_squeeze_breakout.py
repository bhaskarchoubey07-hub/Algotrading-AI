"""Strategy: Bollinger Squeeze & Donchian Breakout
Regime: Transition from Range-Bound / Low-Volatility to High-Volatility Breakout
Detects volatility compression (Bollinger Bandwidth squeeze) and fires an entry
when price pierces the 20-bar Donchian channel.
"""

from typing import Any
import pandas as pd
from app.indicators import calculate_bollinger_bands, calculate_donchian_channels
from app.models import StrategySignal
from .base import BaseStrategy


class BollingerSqueezeBreakoutStrategy(BaseStrategy):
    strategy_id = "bollinger_squeeze_breakout"
    version = "1.0.0"
    description = "Volatility compression alert followed by directional expansion breakout."
    category = "breakout"
    supported_regimes = ["range_bound", "high_volatility", "trending_up", "trending_down"]

    def __init__(self, bb_period: int = 20, bb_std: float = 2.0, donchian_period: int = 20) -> None:
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.donchian_period = donchian_period
        self.parameters = {
            "bb_period": bb_period,
            "bb_std": bb_std,
            "donchian_period": donchian_period,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": "Bollinger Squeeze & Donchian Breakout",
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "regimes": self.supported_regimes,
            "warm_up_bars": max(self.bb_period, self.donchian_period) + 5,
            "supported_segments": ["EQUITY_CASH", "EQUITY_FUTURES", "INDEX"],
            "timeframes": ["5m", "15m", "1h", "1d"],
            "parameters": self.parameters,
            "is_promoted": True,
        }

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        min_bars = max(self.bb_period, self.donchian_period) + 5
        if len(frame) < min_bars:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="flat",
                score=0.0,
                reason=f"Insufficient warm-up: requires {min_bars} bars, got {len(frame)}.",
                regime="uncertain",
            )

        c = frame["close"]
        h = frame["high"]
        l = frame["low"]

        bb = calculate_bollinger_bands(c, period=self.bb_period, num_std=self.bb_std)
        dc = calculate_donchian_channels(h, l, period=self.donchian_period, shift_bars=1)

        curr_close = float(c.iloc[-1])
        curr_high = float(h.iloc[-1])
        curr_low = float(l.iloc[-1])
        donch_up = float(dc.upper.iloc[-1]) if not pd.isna(dc.upper.iloc[-1]) else curr_high + 1
        donch_dn = float(dc.lower.iloc[-1]) if not pd.isna(dc.lower.iloc[-1]) else curr_low - 1
        recent_squeeze = bool(bb.is_squeeze.tail(5).any())

        # Bullish Breakout
        if curr_high >= donch_up:
            conf = 0.85 if recent_squeeze else 0.70
            mid = float(bb.middle.iloc[-1]) if not pd.isna(bb.middle.iloc[-1]) else curr_close * 0.98
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="long",
                score=conf,
                reason=f"Donchian upper channel breakout (₹{donch_up:,.2f}) with squeeze ({recent_squeeze}).",
                suggested_stop=round(mid, 2),
                suggested_target=round(curr_close + 2 * (curr_close - mid), 2),
                regime="high_volatility",
            )

        # Bearish Breakdown
        if curr_low <= donch_dn:
            conf = 0.85 if recent_squeeze else 0.70
            mid = float(bb.middle.iloc[-1]) if not pd.isna(bb.middle.iloc[-1]) else curr_close * 1.02
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="short",
                score=conf,
                reason=f"Donchian lower channel breakdown (₹{donch_dn:,.2f}) with squeeze ({recent_squeeze}).",
                suggested_stop=round(mid, 2),
                suggested_target=round(curr_close - 2 * (mid - curr_close), 2),
                regime="high_volatility",
            )

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_version=self.version,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=str(frame["timestamp"].iloc[-1]),
            direction="flat",
            score=0.25,
            reason="Price remains inside Donchian envelope. Awaiting breakout.",
            regime="range_bound",
        )
