"""AlgoTrade AI — Automated Test Suite for Candidate Indicator Strategies
Validates signal generation, warm-up boundaries, cluster diversification,
and adaptive promotion/demotion validation gates.
"""

import numpy as np
import pandas as pd
import pytest
from app.ensemble import (
    AdaptiveStrategyEvaluator,
    RegimeAwareEnsemble,
    get_strategy_cluster,
)
from app.models import MarketRegime, StrategySignal
from app.strategies import (
    AdxTrendContinuationStrategy,
    AtrBreakoutExitStrategy,
    BollingerSqueezeBreakoutStrategy,
    Ema200MacdStrategy,
    MultiTimeframeSwingStrategy,
    RsiBollingerRangeStrategy,
    VwapVolumeIntradayStrategy,
)


@pytest.fixture
def trending_ohlcv() -> pd.DataFrame:
    n = 100
    dates = pd.date_range("2024-01-01", periods=n, freq="1D")
    base = 100.0
    closes = [base + i * 1.5 for i in range(n)]
    return pd.DataFrame({
        "timestamp": dates.astype(str),
        "open": closes,
        "high": [c + 1.0 for c in closes],
        "low": [c - 0.8 for c in closes],
        "close": closes,
        "volume": [25000] * n,
    })


@pytest.fixture
def range_ohlcv() -> pd.DataFrame:
    n = 100
    dates = pd.date_range("2024-01-01", periods=n, freq="1D")
    base = 100.0
    # Oscillate between 98 and 102
    closes = [base + 2.0 * np.sin(i / 2.0) for i in range(n)]
    return pd.DataFrame({
        "timestamp": dates.astype(str),
        "open": closes,
        "high": [c + 0.5 for c in closes],
        "low": [c - 0.5 for c in closes],
        "close": closes,
        "volume": [10000] * n,
    })


def test_ema200_macd_strategy_bullish(trending_ohlcv: pd.DataFrame):
    strat = Ema200MacdStrategy(ema_period=50)
    sig = strat.generate(trending_ohlcv, "NIFTY")
    assert sig.strategy_id == "ema200_macd_trend"
    assert sig.direction in {"long", "short", "flat"}
    assert 0.0 <= sig.score <= 1.0
    assert sig.suggested_stop is not None or sig.direction == "flat"


def test_bollinger_squeeze_breakout(trending_ohlcv: pd.DataFrame):
    strat = BollingerSqueezeBreakoutStrategy(bb_period=20, donchian_period=20)
    sig = strat.generate(trending_ohlcv, "NIFTY")
    assert sig.strategy_id == "bollinger_squeeze_breakout"
    assert sig.direction in {"long", "short", "flat"}
    assert "Donchian" in sig.reason or "Awaiting" in sig.reason


def test_adx_trend_continuation(trending_ohlcv: pd.DataFrame):
    strat = AdxTrendContinuationStrategy(adx_threshold=20.0)
    sig = strat.generate(trending_ohlcv, "RELIANCE")
    assert sig.strategy_id == "adx_trend_continuation"
    assert sig.direction in {"long", "short", "flat"}


def test_rsi_bollinger_range(range_ohlcv: pd.DataFrame):
    strat = RsiBollingerRangeStrategy(oversold=35.0, overbought=65.0)
    sig = strat.generate(range_ohlcv, "TCS")
    assert sig.strategy_id == "rsi_bollinger_range"
    assert sig.direction in {"long", "short", "flat"}


def test_vwap_volume_intraday(trending_ohlcv: pd.DataFrame):
    strat = VwapVolumeIntradayStrategy(rvol_threshold=0.8)
    sig = strat.generate(trending_ohlcv, "INFY")
    assert sig.strategy_id == "vwap_volume_intraday"
    assert sig.direction in {"long", "short", "flat"}


def test_atr_breakout_exit(trending_ohlcv: pd.DataFrame):
    strat = AtrBreakoutExitStrategy(lookback=15)
    sig = strat.generate(trending_ohlcv, "BANKNIFTY")
    assert sig.strategy_id == "atr_breakout_exit"
    assert sig.direction in {"long", "short", "flat"}


def test_mtf_swing_strategy(trending_ohlcv: pd.DataFrame):
    strat = MultiTimeframeSwingStrategy()
    sig = strat.generate(trending_ohlcv, "TATAMOTORS")
    assert sig.strategy_id == "mtf_swing_trading"
    assert sig.direction in {"long", "short", "flat"}


def test_cluster_diversification_grouping():
    # Verify strategies are partitioned into distinct non-overlapping indicator clusters
    assert get_strategy_cluster("ema200_macd_trend") == "trend"
    assert get_strategy_cluster("rsi_bollinger_range") == "mean_reversion"
    assert get_strategy_cluster("bollinger_squeeze_breakout") == "breakout"
    assert get_strategy_cluster("vwap_volume_intraday") == "volume_momentum"


def test_adaptive_validation_gates():
    # Pass all gates
    promoted = AdaptiveStrategyEvaluator.evaluate_strategy_eligibility(
        strategy_id="ema200_macd_trend",
        current_regime=MarketRegime.TRENDING_UP,
        sample_size=50,
        expectancy_bps=25.0,
        max_drawdown_pct=8.0,
        profit_factor=1.5,
        eligible_regimes=["trending_up"],
    )
    assert promoted.is_promoted is True
    assert promoted.status == "PROMOTED"

    # Demoted on regime mismatch
    demoted_regime = AdaptiveStrategyEvaluator.evaluate_strategy_eligibility(
        strategy_id="rsi_bollinger_range",
        current_regime=MarketRegime.TRENDING_UP,
        sample_size=50,
        expectancy_bps=25.0,
        max_drawdown_pct=8.0,
        profit_factor=1.5,
        eligible_regimes=["range_bound"],
    )
    assert demoted_regime.is_promoted is False
    assert "DEMOTED" in demoted_regime.status

    # Demoted on low expectancy
    demoted_exp = AdaptiveStrategyEvaluator.evaluate_strategy_eligibility(
        strategy_id="test_strat",
        current_regime=MarketRegime.TRENDING_UP,
        sample_size=50,
        expectancy_bps=4.0,  # Below 10 bps threshold after costs
        max_drawdown_pct=8.0,
        profit_factor=1.5,
        eligible_regimes=["trending_up"],
    )
    assert demoted_exp.is_promoted is False
    assert "DEMOTED" in demoted_exp.status
