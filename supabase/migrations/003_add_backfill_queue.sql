-- Migration 003: Add backfill queue table
-- This table holds stocks that need historical data backfilled from DoltHub

CREATE TABLE backfill_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(20) NOT NULL,

    -- Who requested this backfill (for tracking/prioritization)
    requested_by UUID REFERENCES users(id) ON DELETE SET NULL,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Processing status
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),

    -- Priority (higher = more urgent)
    -- Could be based on number of users watching this stock
    priority INTEGER DEFAULT 0,

    -- Processing metadata
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Only one pending request per ticker
    CONSTRAINT unique_ticker_pending UNIQUE(ticker) WHERE status = 'pending'
);

-- Indexes for performance
CREATE INDEX idx_backfill_queue_status ON backfill_queue(status);
CREATE INDEX idx_backfill_queue_ticker ON backfill_queue(ticker);
CREATE INDEX idx_backfill_queue_priority ON backfill_queue(priority DESC, requested_at ASC) WHERE status = 'pending';

-- Updated_at trigger
CREATE TRIGGER update_backfill_queue_updated_at BEFORE UPDATE ON backfill_queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to auto-increment priority when multiple users request same stock
CREATE OR REPLACE FUNCTION increment_backfill_priority()
RETURNS TRIGGER AS $$
BEGIN
    -- If ticker already exists in pending state, increment its priority
    UPDATE backfill_queue
    SET priority = priority + 1,
        updated_at = NOW()
    WHERE ticker = NEW.ticker
      AND status = 'pending'
      AND id != NEW.id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER on_backfill_queue_insert
    AFTER INSERT ON backfill_queue
    FOR EACH ROW EXECUTE FUNCTION increment_backfill_priority();

-- Add comment for documentation
COMMENT ON TABLE backfill_queue IS 'Queue for stocks that need historical data backfilled from DoltHub';
COMMENT ON COLUMN backfill_queue.priority IS 'Higher priority stocks are processed first. Auto-incremented when multiple users request same stock';
