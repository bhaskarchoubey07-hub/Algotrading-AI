"""AlgoTrade AI — Automated Test Suite for Adaptive Strategy Intelligence
Validates finite-state machine transitions, Wilson score confidence bands,
deterioration detection, and dynamic regime weighting.
"""

import pytest
from app.adaptive import (
    AdaptiveWeightEngine,
    StrategyHealthManager,
    StrategyHealthState,
    StrategyPerformanceTracker,
    calculate_wilson_score_interval,
)
from app.models import MarketRegime


def test_strategy_health_state_transitions():
    mgr = StrategyHealthManager()
    mgr.register_strategy("test_strat", StrategyHealthState.CANDIDATE)

    # CANDIDATE -> VALIDATING is legal
    assert mgr.transition_state("test_strat", StrategyHealthState.VALIDATING, "Passed in-sample backtest")
    assert mgr.get_state("test_strat") == StrategyHealthState.VALIDATING

    # VALIDATING -> ACTIVE is legal
    assert mgr.transition_state("test_strat", StrategyHealthState.ACTIVE, "Passed walk-forward paper validation")
    assert mgr.get_state("test_strat") == StrategyHealthState.ACTIVE

    # ACTIVE -> DEGRADED is legal
    assert mgr.transition_state("test_strat", StrategyHealthState.DEGRADED, "Rolling net expectancy breached hurdle")
    assert mgr.get_state("test_strat") == StrategyHealthState.DEGRADED

    # DEGRADED -> CANDIDATE is ILLEGAL (must go to SHADOW, PAUSED, or RETIRED)
    assert not mgr.transition_state("test_strat", StrategyHealthState.CANDIDATE, "Illegal transition attempt")
    # State remains DEGRADED
    assert mgr.get_state("test_strat") == StrategyHealthState.DEGRADED


def test_wilson_score_confidence_interval():
    # 0 trades
    lower, upper = calculate_wilson_score_interval(0, 0)
    assert lower == 0.0 and upper == 100.0

    # 50% win rate on 100 trades -> ~ [40.4%, 59.6%]
    lower, upper = calculate_wilson_score_interval(50, 100)
    assert 40.0 < lower < 41.0
    assert 59.0 < upper < 60.0

    # Small sample: 4 wins out of 5 trades (80% apparent win rate)
    # Wilson interval must reflect high uncertainty: lower bound significantly below 80%
    low_s, high_s = calculate_wilson_score_interval(4, 5)
    assert low_s < 45.0  # Prevents small sample illusion!


def test_performance_tracker_deterioration_detection():
    tracker = StrategyPerformanceTracker(min_sample_size=15, cost_hurdle_bps=10.0)

    # Record 20 consecutive losing trades (-2% return each)
    for _ in range(20):
        tracker.record_trade(
            strategy_id="losing_strat",
            pnl=-2000.0,
            entry_price=100.0,
            exit_price=98.0,
            quantity=10,
            fees=25.0,
        )

    snap = tracker.evaluate_strategy("losing_strat")
    assert snap.trade_count == 20
    assert snap.is_deteriorating is True
    assert len(snap.deterioration_reasons) > 0
    assert snap.win_rate_pct == 0.0
    assert snap.rolling_expectancy_bps < 0.0


def test_adaptive_weight_engine_caps_and_regime():
    we = AdaptiveWeightEngine(max_single_weight=0.35)
    strategy_ids = ["strat_a", "strat_b", "strat_c", "strat_d"]

    # Calculate weights under Trending Up regime
    strategy_regimes = {
        "strat_a": ["trending_up"],
        "strat_b": ["trending_up"],
        "strat_c": ["range_bound"],
        "strat_d": ["range_bound"],
    }

    weights = we.calculate_weights(
        strategy_ids=strategy_ids,
        current_regime=MarketRegime.TRENDING_UP,
        strategy_regimes=strategy_regimes,
        scheme="performance_regime",
    )

    # Sum of weights must equal 1.0 (approx)
    assert pytest.approx(sum(weights.values()), abs=1e-3) == 1.0

    # No individual weight may breach max single cap 35%
    for sid, w in weights.items():
        assert w <= 0.355, f"Strategy {sid} weight {w} exceeded 35% cap"

    # Trending strategies must receive higher weight than range-bound strategies in Trending Up regime
    assert weights["strat_a"] > weights["strat_c"]
