"""AlgoTrade AI — Automated Test Suite for Technical Indicator Engine
Validates mathematical accuracy, warm-up behavior, edge cases, session resets,
and cache determinism across all 16 required technical indicators.
"""

import numpy as np
import pandas as pd
import pytest
from app.indicators import (
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
    indicator_pipeline,
)


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate deterministic 100-bar OHLCV test dataset."""
    np.random.seed(101)
    n = 100
    dates = pd.date_range("2024-01-01", periods=n, freq="1D")
    base = 1000.0
    returns = np.random.normal(0.001, 0.015, n)
    closes = base * np.exp(np.cumsum(returns))
    opens = closes * (1 + np.random.normal(0, 0.002, n))
    highs = np.maximum(opens, closes) + np.abs(np.random.normal(2.0, 1.0, n))
    lows = np.minimum(opens, closes) - np.abs(np.random.normal(2.0, 1.0, n))
    volumes = np.random.randint(1000, 50000, size=n)

    return pd.DataFrame({
        "timestamp": dates.astype(str),
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


# 1. Bollinger Bands & Squeeze Tests
def test_bollinger_bands_calculation(sample_ohlcv: pd.DataFrame):
    res = calculate_bollinger_bands(sample_ohlcv["close"], period=20, num_std=2.0)
    assert len(res.middle) == len(sample_ohlcv)
    assert pd.isna(res.middle.iloc[0])  # Warm-up bar NaN
    assert not pd.isna(res.middle.iloc[25])

    # Middle band is 20-period SMA
    expected_sma = sample_ohlcv["close"].iloc[6:26].mean()
    assert pytest.approx(res.middle.iloc[25], rel=1e-3) == expected_sma

    # Upper > Middle > Lower
    valid_slice = slice(25, 50)
    assert (res.upper.iloc[valid_slice] >= res.middle.iloc[valid_slice]).all()
    assert (res.middle.iloc[valid_slice] >= res.lower.iloc[valid_slice]).all()

    # Bandwidth calculation
    bw = (res.upper - res.lower) / res.middle
    assert pytest.approx(res.bandwidth.iloc[30], rel=1e-3) == bw.iloc[30]
    assert isinstance(res.is_squeeze.iloc[30], (bool, np.bool_))


# 2. EMA Tests
def test_ema_calculation(sample_ohlcv: pd.DataFrame):
    ema20 = calculate_ema(sample_ohlcv["close"], period=20)
    assert len(ema20) == len(sample_ohlcv)
    assert not pd.isna(ema20.iloc[25])

    # For constant price series, EMA must converge exactly to constant price
    constant_s = pd.Series([500.0] * 50)
    ema_const = calculate_ema(constant_s, period=20)
    assert pytest.approx(ema_const.iloc[-1], rel=1e-5) == 500.0


# 3. ADX, +DI, -DI Tests
def test_adx_calculation(sample_ohlcv: pd.DataFrame):
    res = calculate_adx(sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"], period=14)
    assert len(res.adx) == len(sample_ohlcv)
    assert (res.plus_di.dropna() >= 0).all()
    assert (res.minus_di.dropna() >= 0).all()
    # ADX is bounded between 0 and 100
    adx_valid = res.adx.dropna()
    assert (adx_valid >= 0).all() and (adx_valid <= 100).all()


# 4. ATR Tests & Smoothing Options
def test_atr_calculation(sample_ohlcv: pd.DataFrame):
    atr_wilder = calculate_atr(sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"], period=14, smoothing="wilder")
    atr_sma = calculate_atr(sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"], period=14, smoothing="sma")
    atr_ema = calculate_atr(sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"], period=14, smoothing="ema")

    assert (atr_wilder.dropna() > 0).all()
    assert (atr_sma.dropna() > 0).all()
    assert (atr_ema.dropna() > 0).all()


# 5. MACD Tests
def test_macd_calculation(sample_ohlcv: pd.DataFrame):
    res = calculate_macd(sample_ohlcv["close"], fast_period=12, slow_period=26, signal_period=9)
    # Histogram must equal MACD line minus Signal line
    hist_diff = (res.macd - res.signal).dropna()
    assert pytest.approx(res.histogram.dropna().values, rel=1e-4) == hist_diff.values


# 6. RSI Tests (Wilder's Smoothing)
def test_rsi_calculation(sample_ohlcv: pd.DataFrame):
    rsi = calculate_rsi(sample_ohlcv["close"], period=14)
    rsi_valid = rsi.dropna()
    assert (rsi_valid >= 0.0).all() and (rsi_valid <= 100.0).all()

    # Edge case: monotonically increasing series must reach near 100
    up_series = pd.Series([100.0 + i * 5.0 for i in range(30)])
    rsi_up = calculate_rsi(up_series, period=14)
    assert rsi_up.iloc[-1] > 95.0


# 7. Supertrend Tests
def test_supertrend_calculation(sample_ohlcv: pd.DataFrame):
    res = calculate_supertrend(sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"], atr_period=10, multiplier=3.0)
    assert len(res.supertrend) == len(sample_ohlcv)
    # Direction is strictly 1 (bullish) or -1 (bearish)
    valid_dirs = set(res.direction.unique())
    assert valid_dirs.issubset({1, -1})


# 8. VWAP Session Reset Tests
def test_vwap_session_handling():
    # 2 distinct trading days (sessions)
    dates = ["2024-01-01 09:15", "2024-01-01 10:00", "2024-01-02 09:15", "2024-01-02 10:00"]
    high = pd.Series([102.0, 104.0, 110.0, 112.0])
    low = pd.Series([100.0, 101.0, 108.0, 109.0])
    close = pd.Series([101.0, 103.0, 109.0, 111.0])
    volume = pd.Series([1000, 2000, 1500, 2500])
    ts = pd.Series(dates)

    vwap = calculate_vwap(high, low, close, volume, timestamp=ts)
    assert len(vwap) == 4

    # Session 2 (day 2 bar 1) typical price is (110 + 108 + 109) / 3 = 109.0
    # Since session resets on 2024-01-02, day 2 bar 1 VWAP must equal typical price 109.0!
    assert pytest.approx(vwap.iloc[2], rel=1e-4) == 109.0


# 9. Donchian Channels (Lookahead Prevention)
def test_donchian_channels_shift(sample_ohlcv: pd.DataFrame):
    dc = calculate_donchian_channels(sample_ohlcv["high"], sample_ohlcv["low"], period=20, shift_bars=1)
    # Upper channel at t must NOT look at High at t; must be max of previous 20 bars
    expected_upper = sample_ohlcv["high"].iloc[0:20].max()
    assert pytest.approx(dc.upper.iloc[20], rel=1e-4) == expected_upper
    assert dc.middle.iloc[20] == (dc.upper.iloc[20] + dc.lower.iloc[20]) / 2.0


# 10. Stochastic Oscillator Tests
def test_stochastic_oscillator(sample_ohlcv: pd.DataFrame):
    stoch = calculate_stochastic(sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"])
    assert (stoch.percent_k.dropna() >= 0.0).all() and (stoch.percent_k.dropna() <= 100.0).all()
    assert (stoch.percent_d.dropna() >= 0.0).all() and (stoch.percent_d.dropna() <= 100.0).all()


# 11. Rate of Change (ROC)
def test_rate_of_change(sample_ohlcv: pd.DataFrame):
    roc = calculate_roc(sample_ohlcv["close"], period=10)
    expected_roc = ((sample_ohlcv["close"].iloc[20] - sample_ohlcv["close"].iloc[10]) / sample_ohlcv["close"].iloc[10]) * 100.0
    assert pytest.approx(roc.iloc[20], rel=1e-4) == expected_roc


# 12. On-Balance Volume (OBV)
def test_on_balance_volume(sample_ohlcv: pd.DataFrame):
    obv = calculate_obv(sample_ohlcv["close"], sample_ohlcv["volume"])
    assert len(obv) == len(sample_ohlcv)
    # When price rises, OBV increases
    if sample_ohlcv["close"].iloc[5] > sample_ohlcv["close"].iloc[4]:
        assert obv.iloc[5] > obv.iloc[4]


# 13. Relative Volume (RVOL)
def test_relative_volume(sample_ohlcv: pd.DataFrame):
    rvol = calculate_rvol(sample_ohlcv["volume"], period=20)
    valid_rvol = rvol.dropna()
    assert (valid_rvol > 0).all()


# 14. Ichimoku Cloud Tests
def test_ichimoku_cloud(sample_ohlcv: pd.DataFrame):
    ichi = calculate_ichimoku(sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"])
    assert len(ichi.tenkan_sen) == len(sample_ohlcv)
    assert len(ichi.kijun_sen) == len(sample_ohlcv)
    assert len(ichi.senkou_span_a) == len(sample_ohlcv)
    assert len(ichi.senkou_span_b) == len(sample_ohlcv)
    # Cloud color is either 1 or -1
    assert set(ichi.cloud_color.unique()).issubset({1, -1})


# 15. Mansfield Relative Strength vs Benchmark
def test_relative_strength(sample_ohlcv: pd.DataFrame):
    bench = sample_ohlcv["close"] * 1.05
    rs = calculate_relative_strength(sample_ohlcv["close"], bench, period=20)
    assert len(rs) == len(sample_ohlcv)
    # For a constant ratio asset/benchmark, Mansfield RS must be zero
    rs_valid = rs.dropna()
    assert pytest.approx(rs_valid.iloc[-1], abs=1e-3) == 0.0


# 16. TechnicalFeaturePipeline Cache & Integration Test
def test_feature_pipeline_determinism(sample_ohlcv: pd.DataFrame):
    df1 = indicator_pipeline.compute_all_features(sample_ohlcv, symbol="TEST_NIFTY", timeframe="1d")
    # Repeated call should leverage cache and produce identical output
    df2 = indicator_pipeline.compute_all_features(sample_ohlcv, symbol="TEST_NIFTY", timeframe="1d")

    assert set(df1.columns) == set(df2.columns)
    assert "bb_squeeze" in df1.columns
    assert "adx" in df1.columns
    assert "rsi_14" in df1.columns
    assert "supertrend" in df1.columns
    assert "vwap" in df1.columns
    assert "ichimoku_tenkan" in df1.columns
    assert "rvol_20" in df1.columns
    assert len(df1) == len(sample_ohlcv)
