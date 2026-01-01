-- Migration: Add indicator_state and valuation_stats tables for daily feature pipeline
--
-- indicator_state: Stores rolling indicator values for incremental EMA computation
-- valuation_stats: Stores historical valuation percentiles for weekly recomputation

-- =============================================================================
-- indicator_state table
-- Primary key: ticker (one row per ticker)
-- Used for incremental EMA computation and crossover templates
-- =============================================================================
CREATE TABLE indicator_state (
    ticker TEXT PRIMARY KEY,

    -- Last update tracking
    last_price_date DATE NOT NULL,
    last_close DOUBLE PRECISION NULL,

    -- Previous day values (for crossover detection)
    prev_close DOUBLE PRECISION NULL,
    prev_ema_200 DOUBLE PRECISION NULL,
    prev_ema_50 DOUBLE PRECISION NULL,

    -- Current incremental indicators
    ema_200 DOUBLE PRECISION NULL,
    ema_50 DOUBLE PRECISION NULL,

    -- RSI components (optional, for future)
    avg_gain_14 DOUBLE PRECISION NULL,
    avg_loss_14 DOUBLE PRECISION NULL,
    rsi_14 DOUBLE PRECISION NULL,

    -- ATR (optional, for future)
    atr_14 DOUBLE PRECISION NULL,

    -- Window-based values (optional, computed from prices)
    vol_20d DOUBLE PRECISION NULL,
    ret_20d DOUBLE PRECISION NULL,
    ret_252d DOUBLE PRECISION NULL,
    high_52w DOUBLE PRECISION NULL,
    low_52w DOUBLE PRECISION NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create updated_at trigger
CREATE TRIGGER update_indicator_state_updated_at
    BEFORE UPDATE ON indicator_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Index for date-based queries
CREATE INDEX idx_indicator_state_last_price_date ON indicator_state(last_price_date);

-- =============================================================================
-- valuation_stats table
-- Primary key: (ticker, metric, window_days)
-- Stores historical percentiles for valuation templates
-- Recomputed weekly
-- =============================================================================
CREATE TABLE valuation_stats (
    ticker TEXT NOT NULL,
    metric TEXT NOT NULL,  -- e.g., 'ev_ebitda', 'ev_revenue'
    window_days INT NOT NULL,  -- e.g., 1260 (~5 years trading days)

    -- As-of date for this computation
    asof_date DATE NOT NULL,

    -- Distribution statistics
    count INT NOT NULL,
    mean DOUBLE PRECISION NULL,
    std DOUBLE PRECISION NULL,
    min DOUBLE PRECISION NULL,
    max DOUBLE PRECISION NULL,

    -- Percentiles
    p10 DOUBLE PRECISION NULL,
    p20 DOUBLE PRECISION NULL,
    p50 DOUBLE PRECISION NULL,
    p80 DOUBLE PRECISION NULL,
    p90 DOUBLE PRECISION NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    PRIMARY KEY (ticker, metric, window_days)
);

-- Create updated_at trigger
CREATE TRIGGER update_valuation_stats_updated_at
    BEFORE UPDATE ON valuation_stats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Indexes for common queries
CREATE INDEX idx_valuation_stats_ticker ON valuation_stats(ticker);
CREATE INDEX idx_valuation_stats_metric ON valuation_stats(metric);
CREATE INDEX idx_valuation_stats_asof_date ON valuation_stats(asof_date);

-- =============================================================================
-- fundamentals_latest table (optional, for faster daily lookups)
-- Stores latest fundamental data for each ticker
-- =============================================================================
CREATE TABLE IF NOT EXISTS fundamentals_latest (
    ticker TEXT PRIMARY KEY,
    asof_date DATE NOT NULL,

    -- Core financial metrics
    ebitda_ttm DOUBLE PRECISION NULL,
    revenue_ttm DOUBLE PRECISION NULL,
    net_debt DOUBLE PRECISION NULL,
    shares_outstanding DOUBLE PRECISION NULL,

    -- Balance sheet items
    total_debt DOUBLE PRECISION NULL,
    cash_and_equivalents DOUBLE PRECISION NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create updated_at trigger (only if table is newly created)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'update_fundamentals_latest_updated_at'
    ) THEN
        CREATE TRIGGER update_fundamentals_latest_updated_at
            BEFORE UPDATE ON fundamentals_latest
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    END IF;
END $$;

-- Add index
CREATE INDEX IF NOT EXISTS idx_fundamentals_latest_asof_date ON fundamentals_latest(asof_date);

-- =============================================================================
-- Helper view: get active tickers from watchlist_members
-- =============================================================================
CREATE OR REPLACE VIEW active_tickers AS
SELECT DISTINCT e.ticker
FROM watchlists w
JOIN entities e ON w.entity_id = e.id
WHERE w.alerts_enabled = true;

-- =============================================================================
-- Comments for documentation
-- =============================================================================
COMMENT ON TABLE indicator_state IS 'Stores rolling indicator state for incremental EMA computation. One row per ticker.';
COMMENT ON COLUMN indicator_state.last_price_date IS 'Date of the last price update used for this state';
COMMENT ON COLUMN indicator_state.prev_ema_200 IS 'Previous day EMA(200) for crossover detection';
COMMENT ON COLUMN indicator_state.ema_200 IS 'Current EMA(200) value';

COMMENT ON TABLE valuation_stats IS 'Historical valuation distribution stats. Recomputed weekly.';
COMMENT ON COLUMN valuation_stats.window_days IS 'Lookback window in trading days (e.g., 1260 for ~5 years)';
COMMENT ON COLUMN valuation_stats.p20 IS '20th percentile of historical values';
COMMENT ON COLUMN valuation_stats.p80 IS '80th percentile of historical values';

COMMENT ON TABLE fundamentals_latest IS 'Latest fundamental data per ticker for fast daily lookups';
