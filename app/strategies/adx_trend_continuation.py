"""Strategy: ADX-Confirmed Trend Continuation
Regime: Strong Trending Up / Trending Down
Validates that trend strength is non-choppy (ADX > 25) with directional agreement
(+DI > -DI for longs or -DI > +DI for shorts) before entering trend pullbacks.
"""

from typing import Any
import pandas as pd
from app.indicators import calculate_adx, calculate_ema
from app.models import StrategySignal
from .base import BaseStrategy


class AdxTrendContinuationStrategy(BaseStrategy):
    strategy_id = "adx_trend_continuation"
    version = "1.0.0"
    description = "High-conviction trend continuation when ADX indicates strong directional momentum."
    category = "trend"
    supported_regimes = ["trending_up", "trending_down"]

    def __init__(self, adx_threshold: float = 25.0, ema_short: int = 20, ema_long: int = 50) -> None:
        self.adx_threshold = adx_threshold
        self.ema_short = ema_short
        self.ema_long = ema_long
        self.parameters = {
            "adx_threshold": adx_threshold,
            "ema_short": ema_short,
            "ema_long": ema_long,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": "ADX Trend Continuation",
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "regimes": self.supported_regimes,
            "warm_up_bars": max(self.ema_long, 28) + 10,
            "supported_segments": ["EQUITY_CASH", "EQUITY_FUTURES", "INDEX"],
            "timeframes": ["15m", "1h", "1d"],
            "parameters": self.parameters,
            "is_promoted": True,
        }

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        min_bars = 30
        if len(frame) < min_bars:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="flat",
                score=0.0,
                reason=f"Insufficient warm-up: need {min_bars} bars, got {len(frame)}.",
                regime="uncertain",
            )

        c = frame["close"]
        h = frame["high"]
        l = frame["low"]

        effective_long = min(self.ema_long, len(frame) - 5)
        adx_res = calculate_adx(h, l, c, period=14)
        ema20 = calculate_ema(c, period=min(self.ema_short, len(frame) - 5))
        ema50 = calculate_ema(c, period=effective_long)

        curr_close = float(c.iloc[-1])
        curr_adx = float(adx_res.adx.iloc[-1]) if not pd.isna(adx_res.adx.iloc[-1]) else 15.0
        curr_pdi = float(adx_res.plus_di.iloc[-1]) if not pd.isna(adx_res.plus_di.iloc[-1]) else 0.0
        curr_mdi = float(adx_res.minus_di.iloc[-1]) if not pd.isna(adx_res.minus_di.iloc[-1]) else 0.0
        curr_e20 = float(ema20.iloc[-1])
        curr_e50 = float(ema50.iloc[-1])

        # Filter: trend must be strong
        if curr_adx < self.adx_threshold:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="flat",
                score=0.2,
                reason=f"Trend strength weak: ADX is {curr_adx:.1f} (< {self.adx_threshold}).",
                regime="range_bound",
            )

        # Bullish continuation
        if curr_pdi > curr_mdi and curr_e20 >= curr_e50:
            conf = min(0.92, 0.65 + (curr_adx / 100.0) * 0.4)
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="long",
                score=round(conf, 2),
                reason=f"Strong bullish trend: ADX {curr_adx:.1f}, +DI ({curr_pdi:.1f}) > -DI ({curr_mdi:.1f}), price above EMA.",
                suggested_stop=round(curr_e50 * 0.99, 2),
                suggested_target=round(curr_close * 1.05, 2),
                regime="trending_up",
            )

        # Bearish continuation
        if curr_mdi > curr_pdi and curr_e20 <= curr_e50:
            conf = min(0.92, 0.65 + (curr_adx / 100.0) * 0.4)
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="short",
                score=round(conf, 2),
                reason=f"Strong bearish trend: ADX {curr_adx:.1f}, -DI ({curr_mdi:.1f}) > +DI ({curr_pdi:.1f}), price below EMA.",
                suggested_stop=round(curr_e50 * 1.01, 2),
                suggested_target=round(curr_close * 0.95, 2),
                regime="trending_down",
            )

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_version=self.version,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=str(frame["timestamp"].iloc[-1]),
            direction="flat",
            score=0.3,
            reason="Trend direction indicators in conflict with moving average alignment.",
            regime="uncertain",
        )
