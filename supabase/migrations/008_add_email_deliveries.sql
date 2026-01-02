-- Migration 008: Add email_deliveries table for tracking email sends
-- Used by EmailDeliveryService to log all email delivery attempts

CREATE TABLE IF NOT EXISTS email_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    entity_id UUID REFERENCES entities(id) ON DELETE SET NULL,
    to_email TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('sent', 'failed', 'skipped')),
    message_id TEXT,  -- SMTP message ID for tracking
    sent_at TIMESTAMPTZ,
    opened_at TIMESTAMPTZ,  -- Populated via tracking pixel
    error TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,  -- For digest emails, etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_email_deliveries_user_id ON email_deliveries(user_id);
CREATE INDEX IF NOT EXISTS idx_email_deliveries_alert_id ON email_deliveries(alert_id);
CREATE INDEX IF NOT EXISTS idx_email_deliveries_created_at ON email_deliveries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_email_deliveries_status ON email_deliveries(status);

-- RLS policies
ALTER TABLE email_deliveries ENABLE ROW LEVEL SECURITY;

-- Users can only see their own email deliveries
CREATE POLICY "Users can view own email deliveries"
    ON email_deliveries FOR SELECT
    USING (auth.uid() = user_id);

-- Service role can insert (for batch jobs)
CREATE POLICY "Service role can insert email deliveries"
    ON email_deliveries FOR INSERT
    WITH CHECK (true);

-- Comment for documentation
COMMENT ON TABLE email_deliveries IS 'Tracks all email delivery attempts for alerts. Used for metrics, debugging, and open tracking.';
