"""AlgoTrade AI — Adaptive Ensemble Weighting Engine
Calculates normalized, regime-conditioned, risk-budgeted strategy weights
with strict single-strategy allocation caps.
"""

from typing import Literal
from app.models import MarketRegime
from .health import StrategyHealthState, health_manager
from .performance_tracker import StrategyPerformanceSnapshot


class AdaptiveWeightEngine:
    """Computes dynamic voting and capital allocation weights across active strategies."""

    def __init__(self, max_single_weight: float = 0.35) -> None:
        self.max_single_weight = max_single_weight

    def calculate_weights(
        self,
        strategy_ids: list[str],
        current_regime: MarketRegime,
        snapshots: dict[str, StrategyPerformanceSnapshot] | None = None,
        strategy_regimes: dict[str, list[str]] | None = None,
        scheme: Literal["equal", "performance_regime", "drawdown_constrained"] = "performance_regime",
    ) -> dict[str, float]:
        """Compute normalized strategy weights.

        Rules:
        1. Degraded, paused, or retired strategies receive 0 weight.
        2. Strategies matching current regime receive a 1.5x multiplier.
        3. No individual strategy can exceed max_single_weight (35%).
        4. Total sum strictly equals 1.0.
        """
        snapshots = snapshots or {}
        strategy_regimes = strategy_regimes or {}

        # Filter to active eligible strategies (exclude degraded, paused, retired)
        eligible_strategies = [
            sid for sid in strategy_ids
            if health_manager.get_state(sid) not in {
                StrategyHealthState.DEGRADED,
                StrategyHealthState.PAUSED,
                StrategyHealthState.RETIRED,
            }
        ]


        if not eligible_strategies:
            return {sid: 0.0 for sid in strategy_ids}

        raw_weights: dict[str, float] = {}

        if scheme == "equal":
            eq_val = 1.0 / len(eligible_strategies)
            for sid in eligible_strategies:
                raw_weights[sid] = eq_val

        elif scheme == "performance_regime":
            for sid in eligible_strategies:
                snap = snapshots.get(sid)
                exp = max(0.0, snap.rolling_expectancy_bps) if snap else 20.0
                pf = max(1.0, snap.profit_factor) if snap else 1.25
                dd = max(1.0, snap.max_drawdown_pct) if snap else 5.0

                # Base score: expectancy * profit_factor / drawdown
                score = (exp * pf) / dd

                # Regime alignment boost
                eligible_regs = [r.lower() for r in strategy_regimes.get(sid, ["any"])]
                curr_reg = current_regime.value.lower()
                if curr_reg in eligible_regs or "any" in eligible_regs:
                    score *= 1.5
                else:
                    score *= 0.3  # Dampen mismatched regime

                raw_weights[sid] = max(0.01, score)

        else:  # drawdown_constrained
            for sid in eligible_strategies:
                snap = snapshots.get(sid)
                dd = max(1.0, snap.max_drawdown_pct) if snap else 5.0
                raw_weights[sid] = 1.0 / dd

        # Normalization with max cap clipping
        total = sum(raw_weights.values())
        if total <= 0:
            norm_val = 1.0 / len(eligible_strategies)
            return {sid: (norm_val if sid in eligible_strategies else 0.0) for sid in strategy_ids}

        weights = {sid: w / total for sid, w in raw_weights.items()}

        # Cap clipping iteration
        for _ in range(3):
            excess = 0.0
            uncapped_sum = 0.0
            for sid, w in weights.items():
                if w > self.max_single_weight:
                    excess += (w - self.max_single_weight)
                    weights[sid] = self.max_single_weight
                else:
                    uncapped_sum += w

            if excess > 0 and uncapped_sum > 0:
                for sid, w in weights.items():
                    if w < self.max_single_weight:
                        weights[sid] += excess * (w / uncapped_sum)

        # Final re-normalization
        final_total = sum(weights.values())
        final_weights = {
            sid: round(weights.get(sid, 0.0) / final_total, 4) if sid in weights else 0.0
            for sid in strategy_ids
        }
        return final_weights


# Global Adaptive Weight Engine Singleton
weight_engine = AdaptiveWeightEngine()
