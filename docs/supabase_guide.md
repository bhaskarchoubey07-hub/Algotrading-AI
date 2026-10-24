# Supabase PostgreSQL Setup & Migration Guide

AlgoTrade AI uses PostgreSQL with Row Level Security (RLS) for durable multi-tenant persistence.

## Configuration

Set the Supabase credentials in `.env`:
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-supabase-anon-or-service-key
```

When Supabase credentials are not provided, the platform automatically uses the embedded SQLite database (`algotrade_local.db`) with zero manual setup required.

## Applying Versioned Migrations

Execute the migration files in sequence in the **Supabase Dashboard -> SQL Editor**:

1. **`sql/migrations/001_core_schema.sql`**:
   - `profiles`: Trader identity and live approval status.
   - `strategies` & `strategy_versions`: Algorithm version registry.
   - `strategy_configs`: Custom trader parameters and risk allocation.
   - `instruments`: Master NSE contract details, lot sizes, tick sizes.
   - `market_data_metadata`: Historical OHLCV synchronization audit.

2. **`sql/migrations/002_platform_tables.sql`**:
   - `signals`: Strategy emitted signals with confidence score.
   - `ensemble_decisions`: Regime classification and consensus records.
   - `risk_events`: Circuit breaker trips, loss limit breaches.
   - `backtest_runs` & `backtest_metrics`: Reproducible backtest archives.
   - `paper_orders` & `positions`: Persistent simulated execution state.
   - `execution_orders`: Gated live orders audit log.
   - `alerts` & `alert_deliveries`: Multi-channel notification queue.
   - `audit_logs`: Immutable security audit trail.

3. **`sql/migrations/003_row_level_security.sql`**:
   - Implements tenant-level RLS policies on profiles, backtests, orders, and positions to prevent unauthorized access.
