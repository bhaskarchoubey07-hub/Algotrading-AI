import numpy as np
import pandas as pd
from app.models import StrategySignal
from app.strategies.base import BaseStrategy


class AdxMacdStrategy(BaseStrategy):
    strategy_id = "adx_macd"
    version = "1.0.0"
    description = "MACD momentum crossover confirmed by ADX > 25 trend strength."
    category = "trend"
    supported_regimes = ["trending_up", "trending_down"]

    def __init__(self, fast: int = 12, slow: int = 26, signal_span: int = 9, adx_period: int = 14, adx_threshold: float = 25.0) -> None:
        self.fast = fast
        self.slow = slow
        self.signal_span = signal_span
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.parameters = {
            "fast": fast,
            "slow": slow,
            "signal_span": signal_span,
            "adx_period": adx_period,
            "adx_threshold": adx_threshold,
        }

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        min_bars = max(self.slow + self.signal_span, self.adx_period * 2) + 5
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
        high = df["high"]
        low = df["low"]

        # MACD calculation
        ema_fast = close.ewm(span=self.fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal_span, adjust=False).mean()
        hist = macd_line - signal_line

        # ADX calculation
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(window=self.adx_period).mean()
        plus_di = 100 * (pd.Series(plus_dm).rolling(window=self.adx_period).mean() / atr)
        minus_di = 100 * (pd.Series(minus_dm).rolling(window=self.adx_period).mean() / atr)

        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)).fillna(0)
        adx = dx.rolling(window=self.adx_period).mean()

        curr_hist = float(hist.iloc[-1])
        prev_hist = float(hist.iloc[-2])
        curr_adx = float(adx.iloc[-1])
        curr_close = float(close.iloc[-1])
        curr_atr = float(atr.iloc[-1]) if not np.isnan(atr.iloc[-1]) else curr_close * 0.015

        if curr_adx >= self.adx_threshold:
            if curr_hist > 0 and prev_hist <= 0:
                direction = "long"
                score = min(0.95, 0.6 + (curr_adx / 100.0) * 0.35)
                stop = curr_close - 1.5 * curr_atr
                target = curr_close + 3.0 * curr_atr
                reason = f"Bullish MACD crossover confirmed by strong ADX ({curr_adx:.1f} >= {self.adx_threshold})"
            elif curr_hist < 0 and prev_hist >= 0:
                direction = "short"
                score = min(0.95, 0.6 + (curr_adx / 100.0) * 0.35)
                stop = curr_close + 1.5 * curr_atr
                target = curr_close - 3.0 * curr_atr
                reason = f"Bearish MACD crossover confirmed by strong ADX ({curr_adx:.1f} >= {self.adx_threshold})"
            elif curr_hist > 0:
                direction = "long"
                score = 0.65
                stop = curr_close - 1.5 * curr_atr
                target = curr_close + 2.5 * curr_atr
                reason = f"MACD histogram positive with active trend (ADX {curr_adx:.1f})"
            elif curr_hist < 0:
                direction = "short"
                score = 0.65
                stop = curr_close + 1.5 * curr_atr
                target = curr_close - 2.5 * curr_atr
                reason = f"MACD histogram negative with active trend (ADX {curr_adx:.1f})"
            else:
                direction = "flat"
                score = 0.0
                stop, target = None, None
                reason = "MACD neutral"
        else:
            direction = "flat"
            score = 0.0
            stop, target = None, None
            reason = f"Trend too weak for MACD following (ADX {curr_adx:.1f} < {self.adx_threshold})"

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
            regime="trending",
        )
