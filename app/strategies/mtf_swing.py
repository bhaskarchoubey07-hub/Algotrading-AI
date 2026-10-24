"""Strategy: Multi-Timeframe Swing Trading
Regime: TRENDING_UP / TRENDING_DOWN / SWING
Combines higher-timeframe trend alignment (EMA 50 > EMA 200) with lower-timeframe
momentum trigger (Stochastic %K crossover and positive ROC).
"""

from typing import Any
import pandas as pd
from app.indicators import calculate_ema, calculate_roc, calculate_stochastic
from app.models import StrategySignal
from .base import BaseStrategy


class MultiTimeframeSwingStrategy(BaseStrategy):
    strategy_id = "mtf_swing_trading"
    version = "1.0.0"
    description = "Macro trend alignment combined with lower-timeframe stochastic cycle pullbacks."
    category = "swing"
    supported_regimes = ["trending_up", "trending_down"]

    def __init__(self, ema_trend: int = 50, ema_macro: int = 200, roc_period: int = 12) -> None:
        self.ema_trend = ema_trend
        self.ema_macro = ema_macro
        self.roc_period = roc_period
        self.parameters = {
            "ema_trend": ema_trend,
            "ema_macro": ema_macro,
            "roc_period": roc_period,
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": "Multi-Timeframe Swing Momentum",
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "regimes": self.supported_regimes,
            "warm_up_bars": self.ema_macro + 10,
            "supported_segments": ["EQUITY_CASH", "EQUITY_FUTURES"],
            "timeframes": ["1h", "1d"],
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
                reason=f"Insufficient bars for MTF Swing analysis: requires {min_bars} bars.",
                regime="uncertain",
            )

        c = frame["close"]
        h = frame["high"]
        l = frame["low"]

        effective_macro = min(self.ema_macro, len(frame) - 5)
        effective_trend = min(self.ema_trend, len(frame) - 5)

        ema50 = calculate_ema(c, period=effective_trend)
        ema200 = calculate_ema(c, period=effective_macro)
        stoch = calculate_stochastic(h, l, c, k_period=14, d_period=3)
        roc = calculate_roc(c, period=self.roc_period)

        curr_close = float(c.iloc[-1])
        curr_e50 = float(ema50.iloc[-1])
        curr_e200 = float(ema200.iloc[-1])
        curr_k = float(stoch.percent_k.iloc[-1]) if not pd.isna(stoch.percent_k.iloc[-1]) else 50.0
        curr_d = float(stoch.percent_d.iloc[-1]) if not pd.isna(stoch.percent_d.iloc[-1]) else 50.0
        curr_roc = float(roc.iloc[-1]) if not pd.isna(roc.iloc[-1]) else 0.0

        # Bullish Swing: Macro uptrend (Close > EMA 50) + Stochastic turning up + positive ROC
        if curr_close >= curr_e50 and curr_k >= curr_d and curr_roc >= 0:
            conf = min(0.90, 0.70 + (curr_roc / 10.0) * 0.1)
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="long",
                score=round(conf, 2),
                reason=f"MTF Bullish Swing: Close >= EMA 50, Stochastic (%K={curr_k:.1f} >= %D={curr_d:.1f}), positive ROC ({curr_roc:+.2f}%).",
                suggested_stop=round(curr_e50 * 0.985, 2),
                suggested_target=round(curr_close * 1.06, 2),
                regime="trending_up",
            )

        # Bearish Swing: Macro downtrend (Close < EMA 50) + Stochastic turning down + negative ROC
        if curr_close < curr_e50 and curr_k <= curr_d and curr_roc <= 0:
            conf = min(0.90, 0.70 + (abs(curr_roc) / 10.0) * 0.1)
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame["timestamp"].iloc[-1]),
                direction="short",
                score=round(conf, 2),
                reason=f"MTF Bearish Swing: Close < EMA 50, Stochastic (%K={curr_k:.1f} <= %D={curr_d:.1f}), negative ROC ({curr_roc:+.2f}%).",
                suggested_stop=round(curr_e50 * 1.015, 2),
                suggested_target=round(curr_close * 0.94, 2),
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
            reason="No synchronized multi-timeframe swing setup detected.",
            regime="uncertain",
        )
