-- PostgreSQL starter schema. No broker secrets belong in these tables.
CREATE TABLE IF NOT EXISTS strategy_versions (
    id BIGSERIAL PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    version TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(strategy_id, version)
);

CREATE TABLE IF NOT EXISTS market_bars (
    id BIGSERIAL PRIMARY KEY,
    venue TEXT NOT NULL DEFAULT 'NSE',
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    open NUMERIC(18,6) NOT NULL,
    high NUMERIC(18,6) NOT NULL,
    low NUMERIC(18,6) NOT NULL,
    close NUMERIC(18,6) NOT NULL,
    volume NUMERIC(24,4) NOT NULL DEFAULT 0,
    source TEXT NOT NULL,
    UNIQUE(venue, symbol, timeframe, ts, source),
    CHECK(open > 0 AND high > 0 AND low > 0 AND close > 0 AND volume >= 0)
);
CREATE INDEX IF NOT EXISTS idx_market_bars_symbol_time ON market_bars(symbol, timeframe, ts DESC);

CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    strategy_id TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    symbol TEXT NOT NULL,
    segment TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('long','short','flat')),
    score NUMERIC(12,8) NOT NULL,
    reason TEXT NOT NULL,
    market_ts TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS order_intents (
    id BIGSERIAL PRIMARY KEY,
    intent_key TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL CHECK(mode IN ('paper','live')),
    symbol TEXT NOT NULL,
    segment TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('buy','sell')),
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    status TEXT NOT NULL,
    risk_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fills (
    id BIGSERIAL PRIMARY KEY,
    order_intent_id BIGINT NOT NULL REFERENCES order_intents(id),
    fill_quantity INTEGER NOT NULL CHECK(fill_quantity > 0),
    fill_price NUMERIC(18,6) NOT NULL CHECK(fill_price > 0),
    fees NUMERIC(18,6) NOT NULL DEFAULT 0,
    filled_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL CHECK(source IN ('paper','broker'))
);

CREATE TABLE IF NOT EXISTS risk_events (
    id BIGSERIAL PRIMARY KEY,
    severity TEXT NOT NULL CHECK(severity IN ('info','warning','critical')),
    event_type TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
