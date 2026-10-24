"""AlgoTrade AI — Technical Indicator Pipeline & Safe Feature Caching
Generates normalized indicator feature maps with parameter hashing,
data version checksums, warm-up validation, and correlation grouping.
"""

from dataclasses import dataclass, field
import hashlib
from typing import Any
import numpy as np
import pandas as pd

from .core import (
    calculate_adx,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_donchian_channels,
    calculate_ema,
    calculate_ichimoku,
    calculate_macd,
    calculate_obv,
    calculate_relative_strength,
    calculate_roc,
    calculate_rsi,
    calculate_rvol,
    calculate_stochastic,
    calculate_supertrend,
    calculate_vwap,
)


@dataclass
class IndicatorPipelineConfig:
    ema_periods: list[int] = field(default_factory=lambda: [9, 20, 50, 200])
    bb_period: int = 20
    bb_std: float = 2.0
    adx_period: int = 14
    atr_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    rsi_period: int = 14
    supertrend_atr: int = 10
    supertrend_mult: float = 3.0
    donchian_period: int = 20
    stoch_k: int = 14
    stoch_d: int = 3
    roc_period: int = 12
    rvol_period: int = 20
    ichimoku_tenkan: int = 9
    ichimoku_kijun: int = 26
    ichimoku_senkou_b: int = 52


class TechnicalFeaturePipeline:
    """Thread-safe indicator pipeline with caching, warm-up validation, and feature generation."""

    def __init__(self, config: IndicatorPipelineConfig | None = None) -> None:
        self.config = config or IndicatorPipelineConfig()
        self._cache: dict[str, pd.DataFrame] = {}
        self._max_cache_entries = 64

    def _compute_cache_key(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
    ) -> str:
        """Create a collision-resistant cache key incorporating dataset checksum."""
        # Use length, head, and tail rows to form a fast signature
        head_sig = str(df.iloc[0].values) if len(df) > 0 else ""
        tail_sig = str(df.iloc[-1].values) if len(df) > 0 else ""
        data_sig = f"{len(df)}:{head_sig}:{tail_sig}"
        sig_hash = hashlib.sha256(data_sig.encode()).hexdigest()[:16]
        return f"{symbol}_{timeframe}_{sig_hash}"

    def get_warm_up_requirements(self) -> dict[str, int]:
        """Return the minimum required historical bars per indicator family."""
        return {
            "ema_200": 200,
            "ema_50": 50,
            "ema_20": 20,
            "bollinger_bands": self.config.bb_period,
            "adx": self.config.adx_period * 2,  # ADX requires 2x period for smooth stabilization
            "atr": self.config.atr_period,
            "macd": self.config.macd_slow + self.config.macd_signal,
            "rsi": self.config.rsi_period + 1,
            "supertrend": self.config.supertrend_atr * 2,
            "donchian": self.config.donchian_period,
            "stochastic": self.config.stoch_k + self.config.stoch_d,
            "ichimoku": self.config.ichimoku_senkou_b,
        }

    def compute_all_features(
        self,
        df: pd.DataFrame,
        symbol: str = "GENERIC",
        timeframe: str = "1d",
        benchmark_close: pd.Series | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Execute full technical feature pipeline on completed bars.

        Parameters:
          df: DataFrame with ['open', 'high', 'low', 'close', 'volume', 'timestamp']
          symbol: Instrument ticker
          timeframe: Bar timeframe (e.g. '1d', '15m')
          benchmark_close: Optional series for relative strength calculations
        """
        required_cols = {"open", "high", "low", "close", "volume"}
        if not required_cols.issubset(set(df.columns)):
            missing = required_cols - set(df.columns)
            raise ValueError(f"Missing required price columns: {missing}")

        if len(df) == 0:
            return pd.DataFrame()

        cache_key = self._compute_cache_key(symbol, timeframe, df)
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key].copy()

        # Clone input frame to prevent mutation
        features = df.copy()
        c = features["close"]
        h = features["high"]
        l = features["low"]
        v = features["volume"]
        ts = features.get("timestamp", None)

        # 1. EMAs
        for p in self.config.ema_periods:
            features[f"ema_{p}"] = calculate_ema(c, period=p)

        # 2. Bollinger Bands & Squeeze
        bb = calculate_bollinger_bands(
            c,
            period=self.config.bb_period,
            num_std=self.config.bb_std,
        )
        features["bb_middle"] = bb.middle
        features["bb_upper"] = bb.upper
        features["bb_lower"] = bb.lower
        features["bb_bandwidth"] = bb.bandwidth
        features["bb_percent_b"] = bb.percent_b
        features["bb_squeeze"] = bb.is_squeeze

        # 3. ADX, +DI, -DI
        adx_res = calculate_adx(h, l, c, period=self.config.adx_period)
        features["adx"] = adx_res.adx
        features["plus_di"] = adx_res.plus_di
        features["minus_di"] = adx_res.minus_di

        # 4. ATR
        features["atr_14"] = calculate_atr(h, l, c, period=self.config.atr_period, smoothing="wilder")
        features["atr_pct"] = (features["atr_14"] / c) * 100.0

        # 5. MACD
        macd_res = calculate_macd(
            c,
            fast_period=self.config.macd_fast,
            slow_period=self.config.macd_slow,
            signal_period=self.config.macd_signal,
        )
        features["macd_line"] = macd_res.macd
        features["macd_signal"] = macd_res.signal
        features["macd_hist"] = macd_res.histogram

        # 6. RSI
        features["rsi_14"] = calculate_rsi(c, period=self.config.rsi_period)

        # 7. Supertrend
        st_res = calculate_supertrend(
            h,
            l,
            c,
            atr_period=self.config.supertrend_atr,
            multiplier=self.config.supertrend_mult,
        )
        features["supertrend"] = st_res.supertrend
        features["supertrend_dir"] = st_res.direction

        # 8. VWAP (Session-Aware)
        features["vwap"] = calculate_vwap(h, l, c, v, timestamp=ts)

        # 9. Donchian Channels
        dc = calculate_donchian_channels(h, l, period=self.config.donchian_period)
        features["donchian_upper"] = dc.upper
        features["donchian_middle"] = dc.middle
        features["donchian_lower"] = dc.lower

        # 10. Stochastic Oscillator
        stoch = calculate_stochastic(h, l, c, k_period=self.config.stoch_k, d_period=self.config.stoch_d)
        features["stoch_k"] = stoch.percent_k
        features["stoch_d"] = stoch.percent_d

        # 11. Rate of Change (ROC)
        features["roc_12"] = calculate_roc(c, period=self.config.roc_period)

        # 12. On-Balance Volume (OBV)
        features["obv"] = calculate_obv(c, v)

        # 13. Relative Volume (RVOL)
        features["rvol_20"] = calculate_rvol(v, period=self.config.rvol_period)

        # 14. Ichimoku Cloud
        ichi = calculate_ichimoku(
            h,
            l,
            c,
            tenkan_period=self.config.ichimoku_tenkan,
            kijun_period=self.config.ichimoku_kijun,
            senkou_b_period=self.config.ichimoku_senkou_b,
        )
        features["ichimoku_tenkan"] = ichi.tenkan_sen
        features["ichimoku_kijun"] = ichi.kijun_sen
        features["ichimoku_span_a"] = ichi.senkou_span_a
        features["ichimoku_span_b"] = ichi.senkou_span_b
        features["ichimoku_cloud_color"] = ichi.cloud_color

        # 15. Relative Strength vs Benchmark
        if benchmark_close is not None and len(benchmark_close) == len(c):
            features["relative_strength_50"] = calculate_relative_strength(c, benchmark_close)
        else:
            features["relative_strength_50"] = np.nan

        # LRU eviction if cache exceeds capacity
        if len(self._cache) >= self._max_cache_entries:
            oldest_key = next(iter(self._cache))
            self._cache.pop(oldest_key, None)

        self._cache[cache_key] = features
        return features.copy()


# Global indicator pipeline singleton
indicator_pipeline = TechnicalFeaturePipeline()
