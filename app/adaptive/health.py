"""AlgoTrade AI — Adaptive Strategy Health & Lifecycle Engine
Manages formal strategy health state transitions, validation gates,
and shadow evaluation without disrupting open paper positions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any

logger = logging.getLogger("algotrade.adaptive.health")


class StrategyHealthState(str, Enum):
    CANDIDATE = "CANDIDATE"
    VALIDATING = "VALIDATING"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    SHADOW = "SHADOW"
    PAUSED = "PAUSED"
    RETIRED = "RETIRED"
    REACTIVATION_PENDING = "REACTIVATION_PENDING"


# Strict finite-state transition graph
VALID_TRANSITIONS: dict[StrategyHealthState, set[StrategyHealthState]] = {
    StrategyHealthState.CANDIDATE: {
        StrategyHealthState.VALIDATING,
        StrategyHealthState.RETIRED,
    },
    StrategyHealthState.VALIDATING: {
        StrategyHealthState.ACTIVE,
        StrategyHealthState.SHADOW,
        StrategyHealthState.CANDIDATE,
        StrategyHealthState.RETIRED,
    },
    StrategyHealthState.ACTIVE: {
        StrategyHealthState.DEGRADED,
        StrategyHealthState.PAUSED,
        StrategyHealthState.RETIRED,
    },
    StrategyHealthState.DEGRADED: {
        StrategyHealthState.SHADOW,
        StrategyHealthState.PAUSED,
        StrategyHealthState.ACTIVE,
        StrategyHealthState.RETIRED,
    },
    StrategyHealthState.SHADOW: {
        StrategyHealthState.REACTIVATION_PENDING,
        StrategyHealthState.PAUSED,
        StrategyHealthState.RETIRED,
    },
    StrategyHealthState.PAUSED: {
        StrategyHealthState.REACTIVATION_PENDING,
        StrategyHealthState.RETIRED,
    },
    StrategyHealthState.REACTIVATION_PENDING: {
        StrategyHealthState.ACTIVE,
        StrategyHealthState.PAUSED,
        StrategyHealthState.RETIRED,
    },
    StrategyHealthState.RETIRED: set(),  # Terminal state
}


@dataclass
class HealthTransitionRecord:
    strategy_id: str
    from_state: StrategyHealthState
    to_state: StrategyHealthState
    reason: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)


class StrategyHealthManager:
    """Thread-safe lifecycle manager for quantitative strategies."""

    def __init__(self) -> None:
        self._states: dict[str, StrategyHealthState] = {}
        self._history: list[HealthTransitionRecord] = []
        self._shadow_candidates: set[str] = set()

    def register_strategy(
        self,
        strategy_id: str,
        initial_state: StrategyHealthState = StrategyHealthState.ACTIVE,
    ) -> None:
        if strategy_id not in self._states:
            self._states[strategy_id] = initial_state
            self._history.append(
                HealthTransitionRecord(
                    strategy_id=strategy_id,
                    from_state=initial_state,
                    to_state=initial_state,
                    reason="Initial registration in strategy health manager",
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
            )

    def get_state(self, strategy_id: str) -> StrategyHealthState:
        return self._states.get(strategy_id, StrategyHealthState.CANDIDATE)

    def can_transition(
        self, strategy_id: str, target_state: StrategyHealthState
    ) -> bool:
        current = self.get_state(strategy_id)
        return target_state in VALID_TRANSITIONS.get(current, set())

    def transition_state(
        self,
        strategy_id: str,
        target_state: StrategyHealthState,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        current = self.get_state(strategy_id)
        if current == target_state:
            return True

        if not self.can_transition(strategy_id, target_state):
            logger.warning(
                f"Illegal health state transition attempted for {strategy_id}: {current} -> {target_state}"
            )
            return False

        self._states[strategy_id] = target_state
        record = HealthTransitionRecord(
            strategy_id=strategy_id,
            from_state=current,
            to_state=target_state,
            reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )
        self._history.append(record)
        logger.info(
            f"Strategy {strategy_id} transitioned: {current} -> {target_state} | Reason: {reason}"
        )

        if target_state == StrategyHealthState.SHADOW:
            self._shadow_candidates.add(strategy_id)
        else:
            self._shadow_candidates.discard(strategy_id)

        return True

    def get_active_strategies(self) -> list[str]:
        """Return list of strategy IDs currently eligible for paper entry signals."""
        return [
            s_id
            for s_id, st in self._states.items()
            if st == StrategyHealthState.ACTIVE
        ]

    def get_shadow_strategies(self) -> list[str]:
        """Return list of strategy IDs currently undergoing shadow tracking."""
        return list(self._shadow_candidates)

    def get_transition_history(
        self, strategy_id: str | None = None
    ) -> list[HealthTransitionRecord]:
        if strategy_id:
            return [h for h in self._history if h.strategy_id == strategy_id]
        return list(self._history)


# Global Health Manager Singleton
health_manager = StrategyHealthManager()
