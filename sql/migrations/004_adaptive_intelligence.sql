-- 004_adaptive_intelligence.sql: Adaptive Strategy States, Evaluations, Events & Dynamic Weights

CREATE TABLE IF NOT EXISTS strategy_health_states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN (
        'CANDIDATE',
        'VALIDATING',
        'ACTIVE',
        'DEGRADED',
        'SHADOW',
        'PAUSED',
        'RETIRED',
        'REACTIVATION_PENDING'
    )),
    transition_reason TEXT NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_current BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_strat_health_curr ON strategy_health_states(strategy_id, is_current);

CREATE TABLE IF NOT EXISTS strategy_evaluations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id TEXT NOT NULL,
    regime TEXT NOT NULL DEFAULT 'any',
    eval_window_trades INTEGER NOT NULL,
    rolling_expectancy_bps NUMERIC(10,2) NOT NULL,
    win_rate_pct NUMERIC(6,2) NOT NULL,
    win_rate_ci_lower NUMERIC(6,2),
    win_rate_ci_upper NUMERIC(6,2),
    avg_win NUMERIC(18,2) NOT NULL,
    avg_loss NUMERIC(18,2) NOT NULL,
    profit_factor NUMERIC(8,2),
    max_drawdown_pct NUMERIC(6,2) NOT NULL,
    sharpe_ratio NUMERIC(8,2),
    sortino_ratio NUMERIC(8,2),
    turnover_ratio NUMERIC(8,2),
    is_deteriorating BOOLEAN NOT NULL DEFAULT false,
    deterioration_reason TEXT,
    evaluation_ts TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_strat_eval_ts ON strategy_evaluations(strategy_id, evaluation_ts DESC);

CREATE TABLE IF NOT EXISTS adaptation_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    trigger_metric TEXT NOT NULL,
    trigger_value NUMERIC(12,4) NOT NULL,
    threshold_value NUMERIC(12,4) NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    alternative_evaluated TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ensemble_weights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_version TEXT NOT NULL,
    regime TEXT NOT NULL DEFAULT 'all',
    strategy_weights JSONB NOT NULL, -- e.g. {"ema_trend": 0.25, "supertrend": 0.20}
    weighting_scheme TEXT NOT NULL DEFAULT 'performance_regime_weighted',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
