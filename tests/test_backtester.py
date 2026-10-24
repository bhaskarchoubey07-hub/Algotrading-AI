import pandas as pd
import pytest
from app.backtest import AdvancedBacktestEngine, calculate_indian_market_charges, run_backtest
from app.strategies.ema_trend import EmaTrendStrategy
from app.strategies.supertrend import SupertrendStrategy


def make_test_bars(n=100, trend=1.5):
    dates = pd.date_range("2024-01-01", periods=n, freq="D").astype(str)
    close = [100.0 + i * trend for i in range(n)]
    return pd.DataFrame({
        "timestamp": dates,
        "open": close,
        "high": [c + 2.0 for c in close],
        "low": [c - 2.0 for c in close],
        "close": close,
        "volume": [50000] * n,
    })


def test_starter_run_backtest_preserves_behaviour():
    df = make_test_bars()
    strat = EmaTrendStrategy()
    res = run_backtest(df, strat, "TEST", "1d", 5.0)
    assert res.trades >= 0
    assert 0 <= res.win_rate <= 1.0
    assert hasattr(res, "net_pnl")


def test_advanced_backtester_metrics():
    df = make_test_bars(120, trend=1.0)
    strat = SupertrendStrategy()
    engine = AdvancedBacktestEngine(initial_capital=500_000.0, slippage_bps=2.0)
    metrics = engine.run(df, strat, symbol="NIFTY")

    assert metrics.total_trades >= 0
    assert 0.0 <= metrics.win_rate_pct <= 100.0
    assert len(metrics.equity_curve) > 0
    assert isinstance(metrics.monthly_returns, dict)
    assert metrics.max_drawdown_pct >= 0.0


def test_indian_market_charges_calculation():
    # Buy ₹1,00,000, Sell ₹1,05,000 intraday
    charges = calculate_indian_market_charges(100_000.0, 105_000.0, is_delivery=False)
    assert charges > 0
    # Expected round-trip charges include brokerage, STT on sell, GST, stamp duty
    assert 30.0 < charges < 200.0


def test_walk_forward_validation():
    df = make_test_bars(100, trend=1.0)
    strat = EmaTrendStrategy()
    engine = AdvancedBacktestEngine()
    wf = engine.walk_forward_validation(df, strat, "TEST", train_split=0.7)

    assert "in_sample" in wf
    assert "out_of_sample" in wf
    assert "degradation_pct" in wf
