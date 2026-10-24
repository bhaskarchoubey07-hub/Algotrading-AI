import pandas as pd
from app.models import StrategySignal
from app.strategies.base import BaseStrategy


class PriceVolumeMomentumStrategy(BaseStrategy):
    strategy_id = "price_volume_momentum"
    version = "1.0.0"
    description = "Relative price rate-of-change momentum confirmed by significant volume surge."
    category = "momentum"
    supported_regimes = ["trending_up", "trending_down", "high_volatility"]

    def __init__(self, roc_period: int = 10, volume_ma_period: int = 20, volume_factor: float = 1.3) -> None:
        self.roc_period = roc_period
        self.volume_ma_period = volume_ma_period
        self.volume_factor = volume_factor
        self.parameters = {
            "roc_period": roc_period,
            "volume_ma_period": volume_ma_period,
            "volume_factor": volume_factor,
        }

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        min_bars = max(self.roc_period, self.volume_ma_period) + 5
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
        volume = df["volume"]

        # Rate of Change (ROC)
        roc = ((close - close.shift(self.roc_period)) / close.shift(self.roc_period)) * 100.0
        vol_ma = volume.rolling(window=self.volume_ma_period).mean()

        curr_roc = float(roc.iloc[-1])
        curr_vol = float(volume.iloc[-1])
        curr_vol_ma = float(vol_ma.iloc[-1])
        curr_close = float(close.iloc[-1])

        vol_ratio = curr_vol / curr_vol_ma if curr_vol_ma > 0 else 1.0

        if vol_ratio >= self.volume_factor:
            if curr_roc > 2.0:
                direction = "long"
                score = min(0.92, 0.65 + min(curr_roc / 20.0, 0.25))
                stop = curr_close * 0.97
                target = curr_close * 1.06
                reason = f"Bullish momentum surge: ROC +{curr_roc:.1f}% with volume {vol_ratio:.1f}x of 20-MA"
            elif curr_roc < -2.0:
                direction = "short"
                score = min(0.92, 0.65 + min(abs(curr_roc) / 20.0, 0.25))
                stop = curr_close * 1.03
                target = curr_close * 0.94
                reason = f"Bearish momentum dump: ROC {curr_roc:.1f}% with volume {vol_ratio:.1f}x of 20-MA"
            else:
                direction = "flat"
                score = 0.0
                stop, target = None, None
                reason = f"Volume surge present ({vol_ratio:.1f}x) but price change muted (ROC {curr_roc:.1f}%)"
        else:
            direction = "flat"
            score = 0.0
            stop, target = None, None
            reason = f"Insufficient volume confirmation ({vol_ratio:.2f}x < {self.volume_factor}x)"

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
            regime="momentum",
        )
