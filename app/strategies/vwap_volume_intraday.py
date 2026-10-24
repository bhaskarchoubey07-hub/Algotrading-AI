"""Strategy: VWAP & Volume-Confirmed Intraday Research
Regime: INTRADAY / HIGH_VOLATILITY / TRENDING
Analyzes session-anchored Volume-Weighted Average Price (VWAP) deviations
confirmed by institutional volume participation (RVOL > 1.3).
"""

from typing import Any
import pandas as pd
from app.indicators import calculate_rvol, calculate_vwap
from app.models import StrategySignal
from .base import BaseStrategy


class VwapVolumeIntradayStrategy(BaseStrategy):
    strategy_id = "vwap_volume_intraday"
    version = "1.0.0"
    description = "Session-anchored VWAP trend validation confirmed by relative volume spikes."
    category = "momentum"
    supported_regimes = ["trending_up", "trending_down", "high_volatility"]

    def __init__(self, rvol_threshold: float = 1.3, vwap_band_pct: float = 0.003) -> None:
        self.rvol_threshold = rvol_threshold
        self.vwap_band_pct = vwap_band_pct
        self.parameters = {
            "rvol_threshold": rvol_threshold,
            "vwap_band_pct": vwap_band_pct,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": "VWAP & Volume Surge Intraday",
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "regimes": self.supported_regimes,
            "warm_up_bars": 20,
            "supported_segments": ["EQUITY_CASH", "EQUITY_FUTURES", "INDEX"],
            "timeframes": ["1m", "5m", "15m"],
            "parameters": self.parameters,
            "is_promoted": True,
        }

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        min_bars = 20
        if len(frame) < min_bars:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="flat",
                score=0.0,
                reason="Insufficient bars for session VWAP calculation.",
                regime="uncertain",
            )

        c = frame["close"]
        h = frame["high"]
        l = frame["low"]
        v = frame["volume"]
        ts = frame.get("timestamp", None)

        vwap = calculate_vwap(h, l, c, v, timestamp=ts)
        rvol = calculate_rvol(v, period=20)

        curr_close = float(c.iloc[-1])
        curr_vwap = float(vwap.iloc[-1]) if not pd.isna(vwap.iloc[-1]) else curr_close
        curr_rvol = float(rvol.iloc[-1]) if not pd.isna(rvol.iloc[-1]) else 1.0

        # Bullish: Price crossing above VWAP + band with heavy institutional volume (RVOL > threshold)
        if curr_close > curr_vwap * (1.0 + self.vwap_band_pct) and curr_rvol >= self.rvol_threshold:
            conf = min(0.90, 0.65 + (curr_rvol - 1.0) * 0.15)
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="long",
                score=round(conf, 2),
                reason=f"Bullish VWAP surge: Close ₹{curr_close:,.2f} > VWAP ₹{curr_vwap:,.2f} with strong RVOL {curr_rvol:.2f}x.",
                suggested_stop=round(curr_vwap * 0.995, 2),
                suggested_target=round(curr_close * 1.015, 2),
                regime="trending_up",
            )

        # Bearish: Price crossing below VWAP - band with heavy institutional volume (RVOL > threshold)
        if curr_close < curr_vwap * (1.0 - self.vwap_band_pct) and curr_rvol >= self.rvol_threshold:
            conf = min(0.90, 0.65 + (curr_rvol - 1.0) * 0.15)
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="short",
                score=round(conf, 2),
                reason=f"Bearish VWAP breakdown: Close ₹{curr_close:,.2f} < VWAP ₹{curr_vwap:,.2f} with heavy RVOL {curr_rvol:.2f}x.",
                suggested_stop=round(curr_vwap * 1.005, 2),
                suggested_target=round(curr_close * 0.985, 2),
                regime="trending_down",
            )

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_version=self.version,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=str(frame["timestamp"].iloc[-1]),
            direction="flat",
            score=0.2,
            reason=f"RVOL is {curr_rvol:.2f}x (requires >= {self.rvol_threshold}x) or price is near equilibrium VWAP.",
            regime="range_bound",
        )
