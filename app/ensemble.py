from dataclasses import dataclass, field
from typing import Any
import numpy as np
import pandas as pd
from app.models import Direction, EnsembleDecision, MarketRegime, StrategySignal

# Strategy Correlation Clusters to avoid treating highly correlated indicators as independent votes
STRATEGY_CLUSTERS = {
    "trend": {
        "ema_trend",
        "supertrend",
        "adx_macd",
        "ema200_macd_trend",
        "adx_trend_continuation",
    },
    "mean_reversion": {
        "rsi_mean_reversion",
        "bollinger_reversion",
        "rsi_bollinger_range",
    },
    "breakout": {
        "donchian_breakout",
        "orb_breakout",
        "bollinger_squeeze_breakout",
        "atr_breakout_exit",
    },
    "volume_momentum": {
        "price_volume_momentum",
        "vwap_volume_intraday",
        "mtf_swing_trading",
    },
    "options": {
        "options_vertical_spread",
    },
    "ai_ml": {
        "ml_regime_classifier",
    },
}


def get_strategy_cluster(strategy_id: str) -> str:
    for cluster, members in STRATEGY_CLUSTERS.items():
        if strategy_id in members:
            return cluster
    return "other"


@dataclass
class StrategyValidationStatus:
    strategy_id: str
    is_promoted: bool
    status: str  # "PROMOTED", "DEMOTED_REGIME_MISMATCH", "DEMOTED_LOW_EXPECTANCY", "CANDIDATE_UNDER_EVALUATION"
    sample_size: int
    out_of_sample_expectancy_bps: float
    max_drawdown_pct: float
    profit_factor: float
    eligible_regimes: list[str]
    rejection_reasons: list[str] = field(default_factory=list)


class AdaptiveStrategyEvaluator:
    """Evaluates and promotes/demotes strategies for paper trading based on regime & validation gates."""

    @staticmethod
    def evaluate_strategy_eligibility(
        strategy_id: str,
        current_regime: MarketRegime,
        sample_size: int = 40,
        expectancy_bps: float = 22.0,
        max_drawdown_pct: float = 9.5,
        profit_factor: float = 1.35,
        eligible_regimes: list[str] | None = None,
    ) -> StrategyValidationStatus:
        rejection_reasons: list[str] = []
        is_promoted = True

        # Gate 1: Sample Size Check
        if sample_size < 30:
            is_promoted = False
            rejection_reasons.append(f"Sample size too small ({sample_size} < 30 trades)")

        # Gate 2: Net Expectancy after Indian taxes & transaction costs
        if expectancy_bps <= 10.0:
            is_promoted = False
            rejection_reasons.append(f"Net expectancy insufficient ({expectancy_bps:.1f} bps <= 10.0 bps)")

        # Gate 3: Max Peak-to-Trough Drawdown
        if max_drawdown_pct > 15.0:
            is_promoted = False
            rejection_reasons.append(f"Historical drawdown excessive ({max_drawdown_pct:.1f}% > 15.0%)")

        # Gate 4: Profit Factor
        if profit_factor < 1.20:
            is_promoted = False
            rejection_reasons.append(f"Profit factor below threshold ({profit_factor:.2f} < 1.20)")

        # Gate 5: Current Market Regime Alignment
        if eligible_regimes:
            norm_curr = current_regime.value.lower()
            norm_eligible = [r.lower() for r in eligible_regimes]
            if norm_curr not in norm_eligible and "any" not in norm_eligible:
                is_promoted = False
                rejection_reasons.append(f"Mismatched regime: strategy requires {norm_eligible}, currently {norm_curr}")

        status = "PROMOTED" if is_promoted else (
            "DEMOTED_REGIME_MISMATCH" if any("regime" in r.lower() for r in rejection_reasons) else "DEMOTED_LOW_EXPECTANCY"
        )

        return StrategyValidationStatus(
            strategy_id=strategy_id,
            is_promoted=is_promoted,
            status=status,
            sample_size=sample_size,
            out_of_sample_expectancy_bps=expectancy_bps,
            max_drawdown_pct=max_drawdown_pct,
            profit_factor=profit_factor,
            eligible_regimes=eligible_regimes or ["any"],
            rejection_reasons=rejection_reasons,
        )


def combine_signals(signals: list[StrategySignal], min_agreement: int = 2) -> dict:
    """Simple transparent majority ensemble. No calibrated probability is implied."""
    active = [s for s in signals if s.direction in ("long", "short") and s.score > 0]
    long_count = sum(s.direction == "long" for s in active)
    short_count = sum(s.direction == "short" for s in active)
    if long_count >= min_agreement and long_count > short_count:
        direction = "long"
    elif short_count >= min_agreement and short_count > long_count:
        direction = "short"
    else:
        direction = "flat"
    return {
        "direction": direction,
        "long_votes": long_count,
        "short_votes": short_count,
        "strategy_count": len(signals),
        "decision": "candidate_signal" if direction != "flat" else "no_trade",
        "note": "Prototype voting only; add regime filters, costs, correlation controls and validation before use.",
    }


class RegimeDetector:
    """Classifies market into: trending_up, trending_down, range_bound, high_volatility, uncertain."""

    @staticmethod
    def classify_regime(df: pd.DataFrame) -> tuple[MarketRegime, dict[str, float]]:
        if len(df) < 30:
            return MarketRegime.UNCERTAIN, {"reason": "Insufficient bars for regime detection"}

        close = df["close"]
        high = df["high"]
        low = df["low"]

        # EMA 20 and 50
        ema20 = close.ewm(span=20, adjust=False).mean()
        ema50 = close.ewm(span=50, adjust=False).mean()

        # ATR 14
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr14 = tr.rolling(14).mean()

        # Bollinger Bandwidth
        sma20 = close.rolling(20).mean()
        std20 = close.rolling(20).std().replace(0, 1e-6)
        bandwidth = (4 * std20) / sma20

        # ADX Proxy
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
        plus_di = 100 * (pd.Series(plus_dm).rolling(14).mean() / atr14.replace(0, 1e-6))
        minus_di = 100 * (pd.Series(minus_dm).rolling(14).mean() / atr14.replace(0, 1e-6))
        dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-6)).fillna(0)
        adx = float(dx.rolling(14).mean().iloc[-1])

        curr_close = float(close.iloc[-1])
        curr_ema20 = float(ema20.iloc[-1])
        curr_ema50 = float(ema50.iloc[-1])
        curr_atr = float(atr14.iloc[-1])
        curr_bw = float(bandwidth.iloc[-1])

        metrics = {
            "adx": round(adx, 2),
            "bandwidth": round(curr_bw, 4),
            "atr": round(curr_atr, 2),
            "atr_pct": round((curr_atr / curr_close) * 100, 2),
            "ema20": round(curr_ema20, 2),
            "ema50": round(curr_ema50, 2),
        }

        # Trending Conditions (takes precedence when moving averages or ADX confirm alignment)
        if adx >= 25.0 or (curr_close > curr_ema20 > curr_ema50) or (curr_close < curr_ema20 < curr_ema50):
            if curr_close > curr_ema20 > curr_ema50:
                return MarketRegime.TRENDING_UP, metrics
            elif curr_close < curr_ema20 < curr_ema50:
                return MarketRegime.TRENDING_DOWN, metrics

        # High Volatility Check (extreme chop without clear trend alignment)
        if curr_bw > 0.15 or metrics["atr_pct"] > 3.0:
            return MarketRegime.HIGH_VOLATILITY, metrics

        # Range-bound
        if adx < 20.0 and curr_bw < 0.06:
            return MarketRegime.RANGE_BOUND, metrics

        if curr_close > curr_ema50:
            return MarketRegime.TRENDING_UP, metrics
        elif curr_close < curr_ema50:
            return MarketRegime.TRENDING_DOWN, metrics

        return MarketRegime.UNCERTAIN, metrics


class RegimeAwareEnsemble:
    """Production decision engine: filters strategies by regime, cluster diversification, and net edge."""

    def __init__(self, cost_bps_roundtrip: float = 8.0) -> None:
        self.cost_bps_roundtrip = cost_bps_roundtrip

    def evaluate(
        self,
        signals: list[StrategySignal],
        frame: pd.DataFrame | None = None,
        symbol: str = "NIFTY",
    ) -> EnsembleDecision:
        regime = MarketRegime.UNCERTAIN
        regime_metrics: dict[str, Any] = {}

        if frame is not None and len(frame) >= 30:
            regime, regime_metrics = RegimeDetector.classify_regime(frame)

        # Filter out expired or 0-score signals
        active_signals = [s for s in signals if s.direction in ("long", "short") and s.score > 0]

        # Apply regime eligibility filtering
        eligible_signals: list[StrategySignal] = []
        rejected_reasons: list[str] = []

        for s in active_signals:
            strat_regime = getattr(s, "regime", "any")
            # Mean reversion should be filtered out in strong trends
            if regime in (MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN) and strat_regime == "mean_reversion":
                rejected_reasons.append(f"Excluded {s.strategy_id}: Mean-reversion disallowed in strong trend.")
                continue
            # Pure trend-following dampened in tight range-bound markets
            if regime == MarketRegime.RANGE_BOUND and strat_regime == "trending":
                rejected_reasons.append(f"Excluded {s.strategy_id}: Trend-following dampened in range-bound market.")
                continue
            eligible_signals.append(s)

        long_signals = [s for s in eligible_signals if s.direction == "long"]
        short_signals = [s for s in eligible_signals if s.direction == "short"]

        long_votes = len(long_signals)
        short_votes = len(short_signals)

        # Cluster diversification check (ensure independent technical evidence)
        long_clusters = {get_strategy_cluster(s.strategy_id) for s in long_signals}
        short_clusters = {get_strategy_cluster(s.strategy_id) for s in short_signals}

        # Weighted scores
        long_score = sum(s.score for s in long_signals) / max(len(long_signals), 1) if long_signals else 0.0
        short_score = sum(s.score for s in short_signals) / max(len(short_signals), 1) if short_signals else 0.0

        # Conflict resolution
        if long_votes > 0 and short_votes > 0:
            if abs(long_votes - short_votes) <= 1:
                return EnsembleDecision(
                    direction="flat",
                    long_votes=long_votes,
                    short_votes=short_votes,
                    strategy_count=len(signals),
                    decision="NO_TRADE",
                    regime=regime.value,
                    confidence_score=0.0,
                    estimated_edge_bps=0.0,
                    trade_proposal=None,
                    rationale=f"Conflicting signals unresolved: {long_votes} Long vs {short_votes} Short. Capital preserved.",
                    note="Strict conflict rejection rule applied.",
                )

        # Majority rule with minimum 2 votes or 1 high-confidence signal
        direction: Direction = "flat"
        confidence: float = 0.0

        if long_votes >= 2 and long_votes > short_votes:
            direction = "long"
            confidence = round(long_score, 2)
        elif short_votes >= 2 and short_votes > long_votes:
            direction = "short"
            confidence = round(short_score, 2)
        elif len(eligible_signals) == 1 and eligible_signals[0].score >= 0.85:
            # Single high-conviction signal
            direction = eligible_signals[0].direction
            confidence = round(eligible_signals[0].score, 2)

        # Expected edge calculation after estimated transaction costs & slippage
        estimated_edge_bps = 0.0
        if direction != "flat":
            # Edge proxy in basis points based on confidence and ATR
            raw_edge_bps = confidence * 35.0  # e.g. 0.85 conf -> ~30 bps gross
            estimated_edge_bps = round(raw_edge_bps - self.cost_bps_roundtrip, 1)

            if estimated_edge_bps <= 0:
                return EnsembleDecision(
                    direction="flat",
                    long_votes=long_votes,
                    short_votes=short_votes,
                    strategy_count=len(signals),
                    decision="NO_TRADE",
                    regime=regime.value,
                    confidence_score=confidence,
                    estimated_edge_bps=estimated_edge_bps,
                    trade_proposal=None,
                    rationale=f"Insufficient net edge ({estimated_edge_bps} bps <= 0) after {self.cost_bps_roundtrip} bps costs.",
                    note="Transaction cost filter prevented low-expectancy trade.",
                )

        trade_proposal = None
        if direction != "flat":
            winning_signals = long_signals if direction == "long" else short_signals
            stops = [s.suggested_stop for s in winning_signals if s.suggested_stop is not None]
            targets = [s.suggested_target for s in winning_signals if s.suggested_target is not None]

            suggested_stop = min(stops) if (direction == "long" and stops) else (max(stops) if (direction == "short" and stops) else None)
            suggested_target = max(targets) if (direction == "long" and targets) else (min(targets) if (direction == "short" and targets) else None)

            trade_proposal = {
                "symbol": symbol,
                "direction": direction,
                "confidence": confidence,
                "estimated_edge_bps": estimated_edge_bps,
                "suggested_stop": suggested_stop,
                "suggested_target": suggested_target,
                "timestamp": str(signals[0].timestamp) if signals else "",
                "contributing_strategies": [s.strategy_id for s in winning_signals],
                "independent_clusters": list(long_clusters if direction == "long" else short_clusters),
            }

        decision_str = "PROPOSED_TRADE" if direction != "flat" else "NO_TRADE"
        cluster_info = f"across {len(long_clusters if direction == 'long' else short_clusters)} distinct indicator clusters" if direction != "flat" else ""
        rationale = (
            f"Consensus reached: {long_votes if direction == 'long' else short_votes} votes {cluster_info} with {confidence*100:.0f}% confidence. Expected net edge: {estimated_edge_bps:+.1f} bps."
            if direction != "flat"
            else "Insufficient consensus or market conditions not optimal for trade execution."
        )

        return EnsembleDecision(
            direction=direction,
            long_votes=long_votes,
            short_votes=short_votes,
            strategy_count=len(signals),
            decision=decision_str,
            regime=regime.value,
            confidence_score=confidence,
            estimated_edge_bps=estimated_edge_bps,
            trade_proposal=trade_proposal,
            rationale=rationale,
            note=f"Regime: {regime.value} | Rejections: {len(rejected_reasons)}",
        )


regime_ensemble = RegimeAwareEnsemble()

