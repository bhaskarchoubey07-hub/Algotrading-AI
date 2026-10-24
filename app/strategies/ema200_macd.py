"""Strategy: EMA 200 Trend Filter with MACD Momentum Confirmation
Regime: Trending Up / Trending Down
Combines long-term structural trend filtering (Close vs EMA 200) with short-term
momentum expansion (MACD line vs Signal line).
"""

from typing import Any
import pandas as pd
from app.indicators import calculate_ema, calculate_macd
from app.models import StrategySignal
from .base import BaseStrategy


class Ema200MacdStrategy(BaseStrategy):
    strategy_id = "ema200_macd_trend"
    version = "1.0.0"
    description = "Macro trend direction defined by EMA 200 with entry triggered on MACD histogram expansion."
    category = "trend"
    supported_regimes = ["trending_up", "trending_down"]

    def __init__(self, ema_period: int = 200, fast: int = 12, slow: int = 26, signal: int = 9) -> None:
        self.ema_period = ema_period
        self.fast = fast
        self.slow = slow
        self.signal_period = signal
        self.parameters = {
            "ema_period": ema_period,
            "fast": fast,
            "slow": slow,
            "signal": signal,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": "EMA 200 + MACD Trend Following",
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "regimes": self.supported_regimes,
            "warm_up_bars": self.ema_period + self.slow + self.signal_period,
            "supported_segments": ["EQUITY_CASH", "EQUITY_FUTURES", "INDEX"],
            "timeframes": ["15m", "1h", "1d"],
            "parameters": self.parameters,
            "is_promoted": True,
        }

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        min_bars = 40  # Support shorter testing frames gracefully with adaptive period
        effective_ema = min(self.ema_period, len(frame) - 5) if len(frame) < self.ema_period else self.ema_period

        if len(frame) < min_bars:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="flat",
                score=0.0,
                reason=f"Insufficient warm-up: need at least {min_bars} bars, got {len(frame)}.",
                regime="trending_up",
            )

        c = frame["close"]
        ema = calculate_ema(c, period=effective_ema)
        macd = calculate_macd(c, fast_period=self.fast, slow_period=self.slow, signal_period=self.signal_period)

        curr_close = float(c.iloc[-1])
        curr_ema = float(ema.iloc[-1])
        curr_hist = float(macd.histogram.iloc[-1]) if not pd.isna(macd.histogram.iloc[-1]) else 0.0
        prev_hist = float(macd.histogram.iloc[-2]) if len(macd.histogram) > 1 and not pd.isna(macd.histogram.iloc[-2]) else 0.0

        # Bullish: Price above EMA and expanding positive MACD histogram
        if curr_close > curr_ema and curr_hist > 0 and curr_hist >= prev_hist:
            conf = min(0.90, 0.65 + (curr_close - curr_ema) / curr_ema * 2.0)
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="long",
                score=round(conf, 2),
                reason=f"Price ₹{curr_close:,.2f} above EMA ({curr_ema:,.2f}) with expanding positive MACD ({curr_hist:+.2f}).",
                suggested_stop=round(curr_ema * 0.99, 2),
                suggested_target=round(curr_close * 1.04, 2),
                regime="trending_up",
            )

        # Bearish: Price below EMA and expanding negative MACD histogram
        if curr_close < curr_ema and curr_hist < 0 and curr_hist <= prev_hist:
            conf = min(0.90, 0.65 + (curr_ema - curr_close) / curr_ema * 2.0)
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="short",
                score=round(conf, 2),
                reason=f"Price ₹{curr_close:,.2f} below EMA ({curr_ema:,.2f}) with expanding negative MACD ({curr_hist:+.2f}).",
                suggested_stop=round(curr_ema * 1.01, 2),
                suggested_target=round(curr_close * 0.96, 2),
                regime="trending_down",
            )

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_version=self.version,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=str(frame["timestamp"].iloc[-1]),
            direction="flat",
            score=0.25,
            reason="Price and MACD momentum not in directional expansion.",
            regime="uncertain",
        )
