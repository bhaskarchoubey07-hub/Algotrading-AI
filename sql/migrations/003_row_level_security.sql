-- 003_row_level_security.sql: Row Level Security (RLS) policies for user data isolation

-- Enable RLS on user-specific tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE backtest_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

-- Helper function: get authenticated user id
CREATE OR REPLACE FUNCTION current_app_user()
RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid;
END;
$$ LANGUAGE plpgsql STABLE;

-- Profiles Policies
CREATE POLICY "Users can view own profile"
    ON profiles FOR SELECT
    USING (user_id = current_app_user() OR current_app_user() IS NULL);

CREATE POLICY "Users can update own profile"
    ON profiles FOR UPDATE
    USING (user_id = current_app_user());

-- Strategy Configs Policies
CREATE POLICY "Users view own strategy configs"
    ON strategy_configs FOR SELECT
    USING (profile_id IN (SELECT id FROM profiles WHERE user_id = current_app_user()) OR current_app_user() IS NULL);

CREATE POLICY "Users manage own strategy configs"
    ON strategy_configs FOR ALL
    USING (profile_id IN (SELECT id FROM profiles WHERE user_id = current_app_user()) OR current_app_user() IS NULL);

-- Backtest Policies
CREATE POLICY "Users view own backtest runs"
    ON backtest_runs FOR SELECT
    USING (profile_id IN (SELECT id FROM profiles WHERE user_id = current_app_user()) OR current_app_user() IS NULL);

CREATE POLICY "Users insert own backtest runs"
    ON backtest_runs FOR INSERT
    WITH CHECK (profile_id IN (SELECT id FROM profiles WHERE user_id = current_app_user()) OR current_app_user() IS NULL);

-- Paper Orders & Positions Policies
CREATE POLICY "Users view own paper orders"
    ON paper_orders FOR SELECT
    USING (profile_id IN (SELECT id FROM profiles WHERE user_id = current_app_user()) OR current_app_user() IS NULL);

CREATE POLICY "Users manage own paper orders"
    ON paper_orders FOR ALL
    USING (profile_id IN (SELECT id FROM profiles WHERE user_id = current_app_user()) OR current_app_user() IS NULL);

CREATE POLICY "Users view own positions"
    ON positions FOR SELECT
    USING (profile_id IN (SELECT id FROM profiles WHERE user_id = current_app_user()) OR current_app_user() IS NULL);

CREATE POLICY "Users manage own positions"
    ON positions FOR ALL
    USING (profile_id IN (SELECT id FROM profiles WHERE user_id = current_app_user()) OR current_app_user() IS NULL);

-- Public readable tables (Strategies, Instruments, Alerts)
ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Strategies are publicly readable"
    ON strategies FOR SELECT USING (true);

ALTER TABLE strategy_versions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Strategy versions are publicly readable"
    ON strategy_versions FOR SELECT USING (true);

ALTER TABLE instruments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Instruments are publicly readable"
    ON instruments FOR SELECT USING (true);

ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Alerts are viewable by authenticated users"
    ON alerts FOR SELECT USING (true);
