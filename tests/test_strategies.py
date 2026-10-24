import pandas as pd
import pytest
from app.strategies import STRATEGIES
from app.risk import calculate_quantity
from app.ensemble import combine_signals
from app.models import StrategySignal
from app.paper import PaperBroker


def bars(n=80, trend=1.0):
    close = [100 + i * trend + (i % 5) * 0.1 for i in range(n)]
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="D").astype(str),
        "open": close,
        "high": [x + 1 for x in close],
        "low": [x - 1 for x in close],
        "close": close,
        "volume": [10000] * n,
    })


def test_all_strategies_return_valid_signal():
    frame = bars()
    for strategy in STRATEGIES.values():
        signal = strategy.generate(frame, "TEST")
        assert signal.strategy_id == strategy.strategy_id
        assert signal.direction in {"long", "short", "flat"}
        assert 0 <= signal.score <= 1


def test_strategy_rejects_missing_columns():
    with pytest.raises(ValueError, match="Missing OHLCV"):
        STRATEGIES["ema_trend"].generate(pd.DataFrame({"close": [100]}), "TEST")


def test_risk_quantity_is_capped_by_exposure():
    qty = calculate_quantity(equity=100000, entry=500, stop=495)
    assert qty == 20  # 10% maximum notional exposure = ₹10,000


def test_ensemble_requires_two_votes_by_default():
    one = StrategySignal("a", "1", "T", "1d", "t", "long", .8, "test")
    assert combine_signals([one])["direction"] == "flat"
    assert combine_signals([one, one])["direction"] == "long"


def test_paper_broker_never_claims_live_execution():
    broker = PaperBroker()
    order = broker.place_order("RELIANCE", "buy", 1)
    assert order.status == "SIMULATED"
    assert "no broker request sent" in order.note
    with pytest.raises(ValueError):
        broker.place_order("RELIANCE", "buy", 0)
