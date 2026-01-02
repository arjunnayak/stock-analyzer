-- Migration 009: Fix email_deliveries foreign key to reference users table
-- The original migration incorrectly referenced auth.users instead of public.users

-- Drop the incorrect FK constraint
ALTER TABLE email_deliveries
DROP CONSTRAINT IF EXISTS email_deliveries_user_id_fkey;

-- Add correct FK constraint referencing public.users
ALTER TABLE email_deliveries
ADD CONSTRAINT email_deliveries_user_id_fkey
FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
