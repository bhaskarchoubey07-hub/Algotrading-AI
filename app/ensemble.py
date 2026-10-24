from typing import Any
import numpy as np
import pandas as pd
from app.models import Direction, EnsembleDecision, MarketRegime, StrategySignal


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
    """Production decision engine: filters strategies by regime, resolves conflicts, and checks edge."""

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

        # Majority rule with minimum 2 votes or 1 high-confidence AI/ML signal
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
                "participating_strategies": [s.strategy_id for s in winning_signals],
            }

        decision_str = "PROPOSED_TRADE" if direction != "flat" else "NO_TRADE"
        rationale = (
            f"Consensus {direction.upper()} with {max(long_votes, short_votes)} votes in {regime.value} regime (Confidence {confidence:.2f})."
            if direction != "flat"
            else f"No qualified consensus. {long_votes} Long, {short_votes} Short in {regime.value} regime."
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
            note="; ".join(rejected_reasons) if rejected_reasons else "All signal criteria validated.",
        )


regime_ensemble = RegimeAwareEnsemble()
