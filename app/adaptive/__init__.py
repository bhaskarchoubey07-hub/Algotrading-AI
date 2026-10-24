"""AlgoTrade AI — Adaptive Quantitative Intelligence Package"""

from .health import (
    HealthTransitionRecord,
    StrategyHealthManager,
    StrategyHealthState,
    health_manager,
)
from .performance_tracker import (
    StrategyPerformanceSnapshot,
    StrategyPerformanceTracker,
    calculate_wilson_score_interval,
    performance_tracker,
)
from .weights import (
    AdaptiveWeightEngine,
    weight_engine,
)

__all__ = [
    "StrategyHealthState",
    "HealthTransitionRecord",
    "StrategyHealthManager",
    "health_manager",
    "StrategyPerformanceSnapshot",
    "StrategyPerformanceTracker",
    "calculate_wilson_score_interval",
    "performance_tracker",
    "AdaptiveWeightEngine",
    "weight_engine",
]
