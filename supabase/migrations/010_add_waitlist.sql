-- Create waitlist table for landing page email signups
CREATE TABLE IF NOT EXISTS waitlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    plan_interest TEXT CHECK (plan_interest IN ('free', 'paid')) DEFAULT 'free',
    source TEXT DEFAULT 'landing_page',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Index for email lookups
CREATE INDEX IF NOT EXISTS idx_waitlist_email ON waitlist(email);

-- Index for created_at (for analytics)
CREATE INDEX IF NOT EXISTS idx_waitlist_created_at ON waitlist(created_at DESC);

-- Documentation
COMMENT ON TABLE waitlist IS 'Email signups from landing page before account creation';
COMMENT ON COLUMN waitlist.email IS 'User email address';
COMMENT ON COLUMN waitlist.plan_interest IS 'Whether user clicked free or paid CTA';
COMMENT ON COLUMN waitlist.source IS 'Where the signup came from (landing_page, etc)';
COMMENT ON COLUMN waitlist.metadata IS 'Additional tracking data (referrer, utm params, etc)';
