import pandas as pd
import pytest
from app.ensemble import RegimeDetector, RegimeAwareEnsemble, combine_signals
from app.models import MarketRegime, StrategySignal


def test_combine_signals_preserves_behaviour():
    sig1 = StrategySignal("s1", "1", "T", "1d", "t", "long", 0.8, "test")
    assert combine_signals([sig1])["direction"] == "flat"
    assert combine_signals([sig1, sig1])["direction"] == "long"


def test_regime_detector_trending():
    # Construct upward trend
    n = 60
    close = [100.0 + i * 2.0 for i in range(n)]
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D").astype(str),
        "open": close,
        "high": [c + 1.5 for c in close],
        "low": [c - 1.5 for c in close],
        "close": close,
        "volume": [10000] * n,
    })
    regime, metrics = RegimeDetector.classify_regime(df)
    assert regime == MarketRegime.TRENDING_UP
    assert "adx" in metrics


def test_regime_aware_ensemble_resolves_conflict():
    ensemble = RegimeAwareEnsemble()
    sig_long = StrategySignal("s1", "1", "NIFTY", "1d", "t", "long", 0.8, "bullish")
    sig_short = StrategySignal("s2", "1", "NIFTY", "1d", "t", "short", 0.8, "bearish")

    decision = ensemble.evaluate([sig_long, sig_short], symbol="NIFTY")
    assert decision.decision == "NO_TRADE"
    assert decision.direction == "flat"
    assert "Conflicting signals" in decision.rationale


def test_regime_aware_ensemble_consensus():
    ensemble = RegimeAwareEnsemble()
    sig1 = StrategySignal("s1", "1", "NIFTY", "1d", "t", "long", 0.85, "bullish", suggested_stop=24400.0)
    sig2 = StrategySignal("s2", "1", "NIFTY", "1d", "t", "long", 0.90, "bullish", suggested_stop=24350.0)

    decision = ensemble.evaluate([sig1, sig2], symbol="NIFTY")
    assert decision.direction == "long"
    assert decision.decision == "PROPOSED_TRADE"
    assert decision.confidence_score >= 0.85
    assert decision.trade_proposal is not None
    assert decision.trade_proposal["suggested_stop"] == 24350.0
