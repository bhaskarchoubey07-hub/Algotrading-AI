-- 002_platform_tables.sql: Signals, Decisions, Orders, Backtesting & Risk Tables

-- Signals emitted by strategies
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_key TEXT NOT NULL UNIQUE,
    strategy_id TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    symbol TEXT NOT NULL,
    segment TEXT NOT NULL DEFAULT 'EQUITY_CASH',
    timeframe TEXT NOT NULL DEFAULT '1d',
    direction TEXT NOT NULL CHECK(direction IN ('long','short','flat')),
    score NUMERIC(12,8) NOT NULL CHECK(score >= 0 AND score <= 1),
    reason TEXT NOT NULL,
    suggested_stop NUMERIC(18,4),
    suggested_target NUMERIC(18,4),
    regime TEXT NOT NULL DEFAULT 'any',
    market_ts TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_signals_sym_ts ON signals(symbol, market_ts DESC);

-- Ensemble decisions
CREATE TABLE IF NOT EXISTS ensemble_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('long','short','flat')),
    decision TEXT NOT NULL,
    regime TEXT NOT NULL,
    long_votes INTEGER NOT NULL DEFAULT 0,
    short_votes INTEGER NOT NULL DEFAULT 0,
    confidence_score NUMERIC(6,4) NOT NULL DEFAULT 0,
    estimated_edge_bps NUMERIC(8,2) NOT NULL DEFAULT 0,
    trade_proposal JSONB,
    rationale TEXT NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Central risk events
CREATE TABLE IF NOT EXISTS risk_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    severity TEXT NOT NULL CHECK(severity IN ('info','warning','critical')),
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Backtest records
CREATE TABLE IF NOT EXISTS backtest_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID REFERENCES profiles(id),
    strategy_id TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    initial_capital NUMERIC(18,2) NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS backtest_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backtest_run_id UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    total_trades INTEGER NOT NULL DEFAULT 0,
    win_rate_pct NUMERIC(6,2) NOT NULL DEFAULT 0,
    gross_pnl NUMERIC(18,2) NOT NULL DEFAULT 0,
    total_fees NUMERIC(18,2) NOT NULL DEFAULT 0,
    net_pnl NUMERIC(18,2) NOT NULL DEFAULT 0,
    profit_factor NUMERIC(8,2),
    expectancy NUMERIC(18,2) NOT NULL DEFAULT 0,
    max_drawdown_pct NUMERIC(6,2) NOT NULL DEFAULT 0,
    sharpe_ratio NUMERIC(8,2) NOT NULL DEFAULT 0,
    sortino_ratio NUMERIC(8,2) NOT NULL DEFAULT 0,
    cagr_pct NUMERIC(6,2) NOT NULL DEFAULT 0,
    equity_curve JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS backtest_trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backtest_run_id UUID NOT NULL REFERENCES backtest_runs(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    entry_price NUMERIC(18,4) NOT NULL,
    exit_time TIMESTAMPTZ NOT NULL,
    exit_price NUMERIC(18,4) NOT NULL,
    quantity INTEGER NOT NULL,
    gross_pnl NUMERIC(18,2) NOT NULL,
    fees NUMERIC(18,2) NOT NULL,
    net_pnl NUMERIC(18,2) NOT NULL,
    return_pct NUMERIC(8,4) NOT NULL,
    exit_reason TEXT NOT NULL
);

-- Paper orders & fills
CREATE TABLE IF NOT EXISTS paper_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id TEXT NOT NULL UNIQUE,
    profile_id UUID REFERENCES profiles(id),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('buy','sell')),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    order_type TEXT NOT NULL DEFAULT 'MARKET',
    price NUMERIC(18,4) NOT NULL DEFAULT 0,
    fill_price NUMERIC(18,4) NOT NULL DEFAULT 0,
    filled_quantity INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'SIMULATED',
    fees NUMERIC(18,4) NOT NULL DEFAULT 0,
    stop_loss NUMERIC(18,4),
    take_profit NUMERIC(18,4),
    segment TEXT NOT NULL DEFAULT 'EQUITY_CASH',
    strategy_id TEXT NOT NULL DEFAULT 'manual',
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    filled_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS paper_fills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    paper_order_id UUID REFERENCES paper_orders(id) ON DELETE CASCADE,
    fill_quantity INTEGER NOT NULL CHECK(fill_quantity > 0),
    fill_price NUMERIC(18,4) NOT NULL CHECK(fill_price > 0),
    fees NUMERIC(18,4) NOT NULL DEFAULT 0,
    filled_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Positions portfolio
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID REFERENCES profiles(id),
    symbol TEXT NOT NULL,
    segment TEXT NOT NULL DEFAULT 'EQUITY_CASH',
    side TEXT NOT NULL CHECK(side IN ('buy','sell')),
    quantity INTEGER NOT NULL CHECK(quantity >= 0),
    entry_price NUMERIC(18,4) NOT NULL,
    current_price NUMERIC(18,4) NOT NULL,
    stop_loss NUMERIC(18,4),
    take_profit NUMERIC(18,4),
    realized_pnl NUMERIC(18,2) NOT NULL DEFAULT 0,
    unrealized_pnl NUMERIC(18,2) NOT NULL DEFAULT 0,
    strategy_id TEXT NOT NULL DEFAULT 'manual',
    is_open BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(profile_id, symbol, segment)
);

-- Live execution orders & events
CREATE TABLE IF NOT EXISTS execution_orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_intent_key TEXT NOT NULL UNIQUE,
    broker_order_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('buy','sell')),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    price NUMERIC(18,4),
    order_type TEXT NOT NULL,
    status TEXT NOT NULL,
    approval_token_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS execution_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES execution_orders(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Alerts & Deliveries
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL CHECK(category IN ('signal','execution','risk','system')),
    severity TEXT NOT NULL CHECK(severity IN ('info','warning','critical')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alert_deliveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id UUID REFERENCES alerts(id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK(channel IN ('in_app','telegram','email')),
    status TEXT NOT NULL CHECK(status IN ('pending','delivered','failed')),
    error_message TEXT,
    delivered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- User settings & Integration status
CREATE TABLE IF NOT EXISTS user_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE UNIQUE,
    risk_fraction NUMERIC(6,4) NOT NULL DEFAULT 0.0025,
    max_position_fraction NUMERIC(6,4) NOT NULL DEFAULT 0.10,
    max_daily_loss_fraction NUMERIC(6,4) NOT NULL DEFAULT 0.01,
    max_drawdown_fraction NUMERIC(6,4) NOT NULL DEFAULT 0.05,
    telegram_alerts_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    email_alerts_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS integration_status (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    last_ping TIMESTAMPTZ NOT NULL DEFAULT now(),
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Immutable audit log
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
