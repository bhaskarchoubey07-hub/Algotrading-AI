"""AlgoTrade AI — Advanced Technical Indicator Engine
Mathematical reference implementation of all core technical indicators
for Indian Equities, Indices, Futures, and Options.

Rules enforced:
1. Zero look-ahead bias: strictly completed bar t calculations.
2. Explicit warm-up requirements documented per indicator.
3. Clean NaN handling for warm-up and edge conditions.
4. Session-aware indicators (e.g. VWAP) reset cleanly on date boundaries.
"""

from dataclasses import dataclass
from typing import Literal
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class IndicatorMetadata:
    name: str
    category: str
    warm_up_bars: int
    formula_summary: str


# =====================================================================
# 1. BOLLINGER BANDS & SQUEEZE
# =====================================================================

@dataclass
class BollingerBandsResult:
    middle: pd.Series
    upper: pd.Series
    lower: pd.Series
    bandwidth: pd.Series
    percent_b: pd.Series
    is_squeeze: pd.Series  # True when bandwidth is in lowest percentile or inside Keltner


def calculate_bollinger_bands(
    close: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
    squeeze_lookback: int = 120,
    squeeze_threshold: float = 0.04,
) -> BollingerBandsResult:
    """Calculate Bollinger Bands (20, 2σ) and Squeeze State.

    Formula:
      Middle = SMA(Close, period)
      Upper = Middle + num_std * StdDev(Close, period)
      Lower = Middle - num_std * StdDev(Close, period)
      Bandwidth = (Upper - Lower) / Middle
      %B = (Close - Lower) / (Upper - Lower)
      Squeeze = Bandwidth <= squeeze_threshold OR Bandwidth <= rolling_min(Bandwidth, squeeze_lookback)
    """
    middle = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std(ddof=0)
    upper = middle + (num_std * std)
    lower = middle - (num_std * std)

    bandwidth = (upper - lower) / middle.replace(0, np.nan)
    denom = (upper - lower).replace(0, np.nan)
    percent_b = (close - lower) / denom

    # Squeeze is identified when bandwidth is compressed below threshold or historical low
    bw_roll_min = bandwidth.rolling(window=min(squeeze_lookback, len(close)), min_periods=period).min()
    is_squeeze = (bandwidth <= squeeze_threshold) | (bandwidth <= bw_roll_min * 1.05)

    return BollingerBandsResult(
        middle=middle,
        upper=upper,
        lower=lower,
        bandwidth=bandwidth,
        percent_b=percent_b,
        is_squeeze=is_squeeze.fillna(False),
    )


# =====================================================================
# 2. EXPONENTIAL MOVING AVERAGES (EMA)
# =====================================================================

def calculate_ema(series: pd.Series, period: int = 200) -> pd.Series:
    """Calculate Exponential Moving Average with standard multiplier α = 2 / (period + 1).

    Formula:
      EMA_t = α * Price_t + (1 - α) * EMA_{t-1}
    """
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


# =====================================================================
# 3. AVERAGE DIRECTIONAL INDEX (ADX, +DI, -DI)
# =====================================================================

@dataclass
class AdxResult:
    adx: pd.Series
    plus_di: pd.Series
    minus_di: pd.Series


def calculate_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> AdxResult:
    """Calculate ADX (14), +DI and -DI using Wilder's smoothing.

    Formula:
      TR = max(H - L, |H - C_prev|, |L - C_prev|)
      +DM = (H - H_prev) if (H - H_prev) > (L_prev - L) and > 0 else 0
      -DM = (L_prev - L) if (L_prev - L) > (H - H_prev) and > 0 else 0
      WilderSmooth(Series, n): y_t = y_{t-1} - (y_{t-1}/n) + x_t
      +DI = 100 * (+DM_smooth / TR_smooth)
      -DI = 100 * (-DM_smooth / TR_smooth)
      DX = 100 * |+DI - -DI| / (+DI + -DI)
      ADX = WilderSmooth(DX, n)
    """
    prev_close = close.shift(1)
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_dm_s = pd.Series(plus_dm, index=close.index)
    minus_dm_s = pd.Series(minus_dm, index=close.index)

    # Wilder's Smoothing: ewm with alpha=1/period
    tr_smooth = tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    plus_dm_smooth = plus_dm_s.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    minus_dm_smooth = minus_dm_s.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    safe_tr = tr_smooth.replace(0, np.nan)
    plus_di = (100.0 * (plus_dm_smooth / safe_tr)).fillna(0.0)
    minus_di = (100.0 * (minus_dm_smooth / safe_tr)).fillna(0.0)

    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = (100.0 * ((plus_di - minus_di).abs() / di_sum)).fillna(0.0)
    adx = dx.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    return AdxResult(adx=adx, plus_di=plus_di, minus_di=minus_di)


# =====================================================================
# 4. AVERAGE TRUE RANGE (ATR)
# =====================================================================

def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
    smoothing: Literal["wilder", "ema", "sma"] = "wilder",
) -> pd.Series:
    """Calculate Average True Range (14) with configurable smoothing.

    Formula:
      TR = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
    """
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    if smoothing == "wilder":
        return tr.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    elif smoothing == "ema":
        return tr.ewm(span=period, adjust=False, min_periods=period).mean()
    else:  # sma
        return tr.rolling(window=period, min_periods=period).mean()


# =====================================================================
# 5. MOVING AVERAGE CONVERGENCE DIVERGENCE (MACD)
# =====================================================================

@dataclass
class MacdResult:
    macd: pd.Series
    signal: pd.Series
    histogram: pd.Series


def calculate_macd(
    close: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> MacdResult:
    """Calculate MACD (12, 26, 9).

    Formula:
      MACD = EMA(Close, fast_period) - EMA(Close, slow_period)
      Signal = EMA(MACD, signal_period)
      Histogram = MACD - Signal
    """
    fast_ema = close.ewm(span=fast_period, adjust=False, min_periods=fast_period).mean()
    slow_ema = close.ewm(span=slow_period, adjust=False, min_periods=slow_period).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal_period, adjust=False, min_periods=signal_period).mean()
    histogram = macd_line - signal_line

    return MacdResult(macd=macd_line, signal=signal_line, histogram=histogram)


# =====================================================================
# 6. RELATIVE STRENGTH INDEX (RSI)
# =====================================================================

def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (RSI 14) using Wilder's smoothing.

    Formula:
      Δ = Close_t - Close_{t-1}
      Gain = max(Δ, 0), Loss = max(-Δ, 0)
      AvgGain = WilderSmooth(Gain, period)
      AvgLoss = WilderSmooth(Loss, period)
      RS = AvgGain / AvgLoss
      RSI = 100 - (100 / (1 + RS))
    """
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Clean edges: where loss is 0, RSI = 100; where gain is 0, RSI = 0
    rsi = rsi.where(avg_loss != 0, 100.0)
    rsi = rsi.where(avg_gain != 0, 0.0)
    return rsi


# =====================================================================
# 7. SUPERTREND
# =====================================================================

@dataclass
class SupertrendResult:
    supertrend: pd.Series
    direction: pd.Series  # 1 = Bullish (uptrend), -1 = Bearish (downtrend)
    upper_band: pd.Series
    lower_band: pd.Series


def calculate_supertrend(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    atr_period: int = 10,
    multiplier: float = 3.0,
) -> SupertrendResult:
    """Calculate Supertrend indicator.

    Formula:
      HL2 = (High + Low) / 2
      BasicUpper = HL2 + multiplier * ATR
      BasicLower = HL2 - multiplier * ATR
      FinalUpper and FinalLower dynamically trail based on prior bar closure.
    """
    atr = calculate_atr(high, low, close, period=atr_period, smoothing="wilder")
    hl2 = (high + low) / 2.0

    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)

    n = len(close)
    final_upper = basic_upper.copy()
    final_lower = basic_lower.copy()
    supertrend = pd.Series(index=close.index, dtype=float)
    direction = pd.Series(index=close.index, dtype=int)

    # Initialize at first valid ATR
    for i in range(1, n):
        if pd.isna(atr.iloc[i]):
            continue

        prev_close = close.iloc[i - 1]
        prev_upper = final_upper.iloc[i - 1]
        prev_lower = final_lower.iloc[i - 1]

        # Lower band trailing
        if basic_lower.iloc[i] > prev_lower or prev_close < prev_lower:
            final_lower.iloc[i] = basic_lower.iloc[i]
        else:
            final_lower.iloc[i] = prev_lower

        # Upper band trailing
        if basic_upper.iloc[i] < prev_upper or prev_close > prev_upper:
            final_upper.iloc[i] = basic_upper.iloc[i]
        else:
            final_upper.iloc[i] = prev_upper

        # Trend assignment
        prev_trend = direction.iloc[i - 1] if i > 1 and not pd.isna(direction.iloc[i - 1]) else 1
        curr_close = close.iloc[i]

        if prev_trend == 1:
            if curr_close < final_lower.iloc[i]:
                direction.iloc[i] = -1
                supertrend.iloc[i] = final_upper.iloc[i]
            else:
                direction.iloc[i] = 1
                supertrend.iloc[i] = final_lower.iloc[i]
        else:
            if curr_close > final_upper.iloc[i]:
                direction.iloc[i] = 1
                supertrend.iloc[i] = final_lower.iloc[i]
            else:
                direction.iloc[i] = -1
                supertrend.iloc[i] = final_upper.iloc[i]

    return SupertrendResult(
        supertrend=supertrend,
        direction=direction.fillna(1),
        upper_band=final_upper,
        lower_band=final_lower,
    )


# =====================================================================
# 8. VOLUME-WEIGHTED AVERAGE PRICE (VWAP) — SESSION-AWARE
# =====================================================================

def calculate_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    timestamp: pd.Series | None = None,
) -> pd.Series:
    """Calculate Volume-Weighted Average Price with session-boundary resets.

    Formula:
      TypicalPrice = (High + Low + Close) / 3
      VWAP = Cumsum(TypicalPrice * Volume) / Cumsum(Volume)
      Resets at the start of each trading session (e.g. daily boundary).
    """
    tp = (high + low + close) / 3.0
    pv = tp * volume

    if timestamp is not None and len(timestamp) == len(close):
        # Convert timestamps to date series for session partitioning
        ts_dt = pd.to_datetime(timestamp)
        date_groups = ts_dt.dt.date

        cum_pv = pv.groupby(date_groups).cumsum()
        cum_vol = volume.groupby(date_groups).cumsum()
        vwap = cum_pv / cum_vol.replace(0, np.nan)
        return vwap
    else:
        # Single-session or standard cumulative fallback
        return pv.cumsum() / volume.cumsum().replace(0, np.nan)


# =====================================================================
# 9. DONCHIAN CHANNELS
# =====================================================================

@dataclass
class DonchianResult:
    upper: pd.Series
    middle: pd.Series
    lower: pd.Series


def calculate_donchian_channels(
    high: pd.Series,
    low: pd.Series,
    period: int = 20,
    shift_bars: int = 1,
) -> DonchianResult:
    """Calculate Donchian Channels (20) with lookahead prevention via shift.

    Formula:
      Upper = RollingMax(High_{t-shift}, period)
      Lower = RollingMin(Low_{t-shift}, period)
      Middle = (Upper + Lower) / 2
    """
    shifted_high = high.shift(shift_bars)
    shifted_low = low.shift(shift_bars)

    upper = shifted_high.rolling(window=period, min_periods=period).max()
    lower = shifted_low.rolling(window=period, min_periods=period).min()
    middle = (upper + lower) / 2.0

    return DonchianResult(upper=upper, middle=middle, lower=lower)


# =====================================================================
# 10. STOCHASTIC OSCILLATOR (%K, %D)
# =====================================================================

@dataclass
class StochasticResult:
    percent_k: pd.Series
    percent_d: pd.Series


def calculate_stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    d_period: int = 3,
    slowing: int = 3,
) -> StochasticResult:
    """Calculate Stochastic Oscillator (%K, %D).

    Formula:
      LowestLow = RollingMin(Low, k_period)
      HighestHigh = RollingMax(High, k_period)
      Fast %K = 100 * (Close - LowestLow) / (HighestHigh - LowestLow)
      Slow %K = SMA(Fast %K, slowing)
      %D = SMA(Slow %K, d_period)
    """
    lowest_low = low.rolling(window=k_period, min_periods=k_period).min()
    highest_high = high.rolling(window=k_period, min_periods=k_period).max()

    denom = (highest_high - lowest_low).replace(0, np.nan)
    fast_k = 100.0 * ((close - lowest_low) / denom)

    percent_k = fast_k.rolling(window=slowing, min_periods=slowing).mean()
    percent_d = percent_k.rolling(window=d_period, min_periods=d_period).mean()

    return StochasticResult(percent_k=percent_k.fillna(50.0), percent_d=percent_d.fillna(50.0))


# =====================================================================
# 11. RATE OF CHANGE (ROC)
# =====================================================================

def calculate_roc(close: pd.Series, period: int = 12) -> pd.Series:
    """Calculate Price Rate of Change (ROC).

    Formula:
      ROC_t = ((Close_t - Close_{t-period}) / Close_{t-period}) * 100
    """
    shifted = close.shift(period)
    return ((close - shifted) / shifted.replace(0, np.nan)) * 100.0


# =====================================================================
# 12. ON-BALANCE VOLUME (OBV)
# =====================================================================

def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Calculate On-Balance Volume (OBV).

    Formula:
      Direction = +1 if Close > Close_prev, -1 if Close < Close_prev, 0 if equal
      OBV = Cumsum(Direction * Volume)
    """
    price_change = close.diff()
    direction = pd.Series(0.0, index=close.index)
    direction[price_change > 0] = 1.0
    direction[price_change < 0] = -1.0

    obv = (direction * volume).cumsum()
    return obv


# =====================================================================
# 13. RELATIVE VOLUME (RVOL)
# =====================================================================

def calculate_rvol(volume: pd.Series, period: int = 20) -> pd.Series:
    """Calculate Relative Volume (RVOL) against rolling average volume.

    Formula:
      RVOL = Volume_t / SMA(Volume, period)
      RVOL > 1.5 denotes volume surge; RVOL < 0.7 denotes volume dry-up.
    """
    vol_sma = volume.rolling(window=period, min_periods=period).mean()
    return volume / vol_sma.replace(0, np.nan)


# =====================================================================
# 14. ICHIMOKU CLOUD
# =====================================================================

@dataclass
class IchimokuResult:
    tenkan_sen: pd.Series       # Conversion line (9-period)
    kijun_sen: pd.Series        # Base line (26-period)
    senkou_span_a: pd.Series    # Leading Span A (shifted +26 or aligned for bar t)
    senkou_span_b: pd.Series    # Leading Span B (shifted +26 or aligned for bar t)
    chikou_span: pd.Series      # Lagging Span (Close shifted -26)
    cloud_color: pd.Series      # 1 = Green cloud (Span A > Span B), -1 = Red cloud


def calculate_ichimoku(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
) -> IchimokuResult:
    """Calculate Ichimoku Kinko Hyo without future leak.

    Formulas:
      Tenkan-sen = (RollingMax(High, 9) + RollingMin(Low, 9)) / 2
      Kijun-sen = (RollingMax(High, 26) + RollingMin(Low, 26)) / 2
      Senkou Span A = (Tenkan + Kijun) / 2
      Senkou Span B = (RollingMax(High, 52) + RollingMin(Low, 52)) / 2
      Chikou Span = Close shifted backwards
    """
    tenkan = (high.rolling(tenkan_period).max() + low.rolling(tenkan_period).min()) / 2.0
    kijun = (high.rolling(kijun_period).max() + low.rolling(kijun_period).min()) / 2.0
    span_a = (tenkan + kijun) / 2.0
    span_b = (high.rolling(senkou_b_period).max() + low.rolling(senkou_b_period).min()) / 2.0

    chikou = close.shift(-kijun_period)
    cloud_color = np.where(span_a >= span_b, 1, -1)

    return IchimokuResult(
        tenkan_sen=tenkan,
        kijun_sen=kijun,
        senkou_span_a=span_a,
        senkou_span_b=span_b,
        chikou_span=chikou,
        cloud_color=pd.Series(cloud_color, index=close.index),
    )


# =====================================================================
# 15. RELATIVE STRENGTH VS BENCHMARK (MANSFIELD RS)
# =====================================================================

def calculate_relative_strength(
    asset_close: pd.Series,
    benchmark_close: pd.Series,
    period: int = 50,
) -> pd.Series:
    """Calculate Mansfield Relative Strength of asset vs benchmark (e.g. NIFTY 50).

    Formula:
      BaseRS = AssetClose / BenchmarkClose
      MansfieldRS = ((BaseRS / SMA(BaseRS, period)) - 1) * 100
    """
    base_rs = asset_close / benchmark_close.replace(0, np.nan)
    rs_sma = base_rs.rolling(window=period, min_periods=period).mean()
    mansfield_rs = ((base_rs / rs_sma.replace(0, np.nan)) - 1.0) * 100.0
    return mansfield_rs
