-- Create users table
-- For MVP, keep it simple - we'll use Supabase auth later
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- User preferences
    investing_style VARCHAR(50) CHECK (investing_style IN ('value', 'growth', 'blend')),
    alerts_enabled BOOLEAN DEFAULT TRUE,

    -- Metadata
    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- Create entities table (stocks)
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255),
    sector VARCHAR(100),

    -- Metadata for tracking data availability
    has_price_data BOOLEAN DEFAULT FALSE,
    has_fundamental_data BOOLEAN DEFAULT FALSE,

    -- R2 data tracking
    price_data_min_date DATE,
    price_data_max_date DATE,
    fundamental_data_min_date DATE,
    fundamental_data_max_date DATE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_data_update TIMESTAMP WITH TIME ZONE,

    CONSTRAINT ticker_uppercase CHECK (ticker = UPPER(ticker))
);

-- Create watchlists table (user <-> entity many-to-many)
CREATE TABLE watchlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,

    -- When was this stock added to watchlist
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- User can temporarily pause alerts for specific stocks
    alerts_enabled BOOLEAN DEFAULT TRUE,

    CONSTRAINT unique_user_entity UNIQUE(user_id, entity_id)
);

-- Create user_entity_settings table
-- Stores per-user, per-stock configuration and state tracking
CREATE TABLE user_entity_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,

    -- State tracking for alerts (critical for stateful monitoring)
    -- Valuation regime state
    last_valuation_regime VARCHAR(50),  -- e.g., 'cheap', 'expensive', 'normal'
    last_valuation_percentile DECIMAL(5,2),

    -- Fundamental state
    last_eps_direction VARCHAR(20),  -- e.g., 'positive', 'negative', 'neutral'
    last_eps_value DECIMAL(20,4),

    -- Technical state
    last_trend_position VARCHAR(20),  -- e.g., 'above_200dma', 'below_200dma'
    last_price_close DECIMAL(20,4),

    -- Last evaluation timestamp
    last_evaluated_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT unique_user_entity_settings UNIQUE(user_id, entity_id)
);

-- Create alert_history table
-- Track all alerts sent to users
CREATE TABLE alert_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,

    -- Alert details
    alert_type VARCHAR(50) NOT NULL,  -- e.g., 'valuation_regime_change', 'fundamental_inflection', 'trend_break'
    headline TEXT NOT NULL,
    what_changed TEXT,
    why_it_matters TEXT,
    before_vs_now TEXT,
    what_didnt_change TEXT,

    -- Delivery tracking
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    opened_at TIMESTAMP WITH TIME ZONE,

    -- Associated data snapshot
    data_snapshot JSONB,

    CONSTRAINT valid_alert_type CHECK (alert_type IN ('valuation_regime_change', 'fundamental_inflection', 'trend_break'))
);

-- Create indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_entities_ticker ON entities(ticker);
CREATE INDEX idx_watchlists_user_id ON watchlists(user_id);
CREATE INDEX idx_watchlists_entity_id ON watchlists(entity_id);
CREATE INDEX idx_user_entity_settings_user_id ON user_entity_settings(user_id);
CREATE INDEX idx_user_entity_settings_entity_id ON user_entity_settings(entity_id);
CREATE INDEX idx_alert_history_user_id ON alert_history(user_id);
CREATE INDEX idx_alert_history_entity_id ON alert_history(entity_id);
CREATE INDEX idx_alert_history_sent_at ON alert_history(sent_at DESC);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entities_updated_at BEFORE UPDATE ON entities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_entity_settings_updated_at BEFORE UPDATE ON user_entity_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert some test data for development
INSERT INTO users (email, investing_style) VALUES
    ('test@example.com', 'blend'),
    ('value@example.com', 'value')
ON CONFLICT (email) DO NOTHING;

INSERT INTO entities (ticker, name, sector) VALUES
    ('AAPL', 'Apple Inc.', 'Technology'),
    ('MSFT', 'Microsoft Corporation', 'Technology'),
    ('GOOGL', 'Alphabet Inc.', 'Technology'),
    ('TSLA', 'Tesla, Inc.', 'Automotive'),
    ('NVDA', 'NVIDIA Corporation', 'Technology')
ON CONFLICT (ticker) DO NOTHING;

-- Add test user watchlist
INSERT INTO watchlists (user_id, entity_id)
SELECT u.id, e.id
FROM users u
CROSS JOIN entities e
WHERE u.email = 'test@example.com'
ON CONFLICT (user_id, entity_id) DO NOTHING;
