"""AlgoTrade AI — Adaptive Performance Tracking & Strategy Deterioration Detection
Calculates rolling statistical quality metrics, Wilson score confidence intervals,
and triggers automatic deterioration warnings.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import numpy as np


@dataclass
class StrategyPerformanceSnapshot:
    strategy_id: str
    trade_count: int
    net_pnl: float
    rolling_expectancy_bps: float
    win_rate_pct: float
    win_rate_ci_lower: float
    win_rate_ci_upper: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    is_deteriorating: bool = False
    deterioration_reasons: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def calculate_wilson_score_interval(
    successes: int,
    total: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Calculate Wilson score interval for binomial proportions (win rate).

    Formula prevents false certainty in small samples.
    """
    if total <= 0:
        return 0.0, 100.0

    z = 1.95996  # 95% two-tailed normal critical value
    p = successes / total

    denominator = 1.0 + (z**2 / total)
    centre_adjusted_probability = p + (z**2 / (2.0 * total))
    adjusted_std_dev = math.sqrt((p * (1.0 - p) / total) + (z**2 / (4.0 * total**2)))

    lower_bound = (centre_adjusted_probability - z * adjusted_std_dev) / denominator
    upper_bound = (centre_adjusted_probability + z * adjusted_std_dev) / denominator

    return max(0.0, lower_bound * 100.0), min(100.0, upper_bound * 100.0)


class StrategyPerformanceTracker:
    """Monitors closed paper trades and evaluates strategy statistical health."""

    def __init__(self, min_sample_size: int = 15, cost_hurdle_bps: float = 10.0) -> None:
        self.min_sample_size = min_sample_size
        self.cost_hurdle_bps = cost_hurdle_bps
        self._trade_records: dict[str, list[dict]] = {}

    def record_trade(
        self,
        strategy_id: str,
        pnl: float,
        entry_price: float,
        exit_price: float,
        quantity: int,
        fees: float = 0.0,
        regime: str = "any",
    ) -> None:
        if strategy_id not in self._trade_records:
            self._trade_records[strategy_id] = []

        return_pct = ((exit_price - entry_price) / entry_price) * 100.0
        self._trade_records[strategy_id].append({
            "pnl": pnl,
            "return_pct": return_pct,
            "fees": fees,
            "net_pnl": pnl - fees,
            "regime": regime,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def evaluate_strategy(
        self,
        strategy_id: str,
        rolling_window: int = 40,
    ) -> StrategyPerformanceSnapshot:
        trades = self._trade_records.get(strategy_id, [])
        if not trades:
            # Return baseline prior
            return StrategyPerformanceSnapshot(
                strategy_id=strategy_id,
                trade_count=0,
                net_pnl=0.0,
                rolling_expectancy_bps=0.0,
                win_rate_pct=50.0,
                win_rate_ci_lower=25.0,
                win_rate_ci_upper=75.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=1.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                is_deteriorating=False,
                deterioration_reasons=["No closed trades recorded yet"],
            )

        window_trades = trades[-rolling_window:]
        n = len(window_trades)
        net_pnls = [t["net_pnl"] for t in window_trades]
        wins = [p for p in net_pnls if p > 0]
        losses = [abs(p) for p in net_pnls if p < 0]

        win_count = len(wins)
        win_rate = (win_count / n) * 100.0
        ci_lower, ci_upper = calculate_wilson_score_interval(win_count, n)

        avg_win = float(np.mean(wins)) if wins else 0.0
        avg_loss = float(np.mean(losses)) if losses else 0.0
        gross_win = sum(wins)
        gross_loss = sum(losses)
        profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (2.0 if gross_win > 0 else 1.0)

        # Net expectancy in basis points (normalized by trade value)
        returns = [t["return_pct"] for t in window_trades]
        mean_ret = float(np.mean(returns)) if returns else 0.0
        std_ret = float(np.std(returns)) if len(returns) > 1 else 1.0
        expectancy_bps = mean_ret * 100.0  # 1% return = 100 bps

        # Drawdown computation
        cum_pnl = np.cumsum(net_pnls)
        running_max = np.maximum.accumulate(cum_pnl)
        drawdowns = running_max - cum_pnl
        max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0
        peak = float(np.max(running_max)) if len(running_max) > 0 and np.max(running_max) > 0 else 1.0
        max_dd_pct = (max_dd / peak) * 100.0 if peak > 0 else 0.0

        # Sharpe / Sortino
        sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0.0
        downside_returns = [r for r in returns if r < 0]
        downside_std = float(np.std(downside_returns)) if len(downside_returns) > 1 else 1.0
        sortino = (mean_ret / downside_std * math.sqrt(252)) if downside_std > 0 else 0.0

        # Deterioration Detection Logic
        deterioration_reasons: list[str] = []
        is_deteriorating = False

        if n >= self.min_sample_size:
            if expectancy_bps < self.cost_hurdle_bps:
                is_deteriorating = True
                deterioration_reasons.append(
                    f"Rolling net expectancy ({expectancy_bps:.1f} bps) fallen below hurdle ({self.cost_hurdle_bps:.1f} bps)"
                )
            if max_dd_pct > 12.0:
                is_deteriorating = True
                deterioration_reasons.append(
                    f"Rolling drawdown ({max_dd_pct:.1f}%) breached 12.0% risk boundary"
                )
            if ci_lower < 35.0:
                is_deteriorating = True
                deterioration_reasons.append(
                    f"Lower 95% win rate confidence bound ({ci_lower:.1f}%) dropped below 35.0%"
                )
            if profit_factor < 1.05:
                is_deteriorating = True
                deterioration_reasons.append(
                    f"Profit factor ({profit_factor:.2f}) degraded to near break-even"
                )

        return StrategyPerformanceSnapshot(
            strategy_id=strategy_id,
            trade_count=n,
            net_pnl=round(sum(net_pnls), 2),
            rolling_expectancy_bps=round(expectancy_bps, 2),
            win_rate_pct=round(win_rate, 2),
            win_rate_ci_lower=round(ci_lower, 2),
            win_rate_ci_upper=round(ci_upper, 2),
            avg_win=round(avg_win, 2),
            avg_loss=round(avg_loss, 2),
            profit_factor=round(profit_factor, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            is_deteriorating=is_deteriorating,
            deterioration_reasons=deterioration_reasons,
        )


# Global Performance Tracker Singleton
performance_tracker = StrategyPerformanceTracker()
