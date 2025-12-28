-- Migration: Integrate Supabase Auth with existing users table
-- This migration adds auth_id to link users table with Supabase auth.users

-- Add auth_id column to users table
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS auth_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- Add unique constraint on auth_id
ALTER TABLE users
  ADD CONSTRAINT IF NOT EXISTS unique_auth_id UNIQUE(auth_id);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_users_auth_id ON users(auth_id);

-- Function to auto-create user record when someone signs up
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.users (auth_id, email, created_at, updated_at, alerts_enabled)
  VALUES (NEW.id, NEW.email, NOW(), NOW(), TRUE)
  ON CONFLICT (auth_id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to auto-create user record on signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();

-- Function to sync email updates from auth.users to users table
CREATE OR REPLACE FUNCTION handle_user_email_update()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE public.users
  SET email = NEW.email, updated_at = NOW()
  WHERE auth_id = NEW.id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to sync email updates
DROP TRIGGER IF EXISTS on_auth_user_email_updated ON auth.users;
CREATE TRIGGER on_auth_user_email_updated
  AFTER UPDATE OF email ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_user_email_update();

-- Enable Row Level Security (RLS)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE watchlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_entity_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_history ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist
DROP POLICY IF EXISTS "Users can view own data" ON users;
DROP POLICY IF EXISTS "Users can update own data" ON users;
DROP POLICY IF EXISTS "Users can view own watchlists" ON watchlists;
DROP POLICY IF EXISTS "Users can insert own watchlists" ON watchlists;
DROP POLICY IF EXISTS "Users can delete own watchlists" ON watchlists;
DROP POLICY IF EXISTS "Users can update own watchlists" ON watchlists;
DROP POLICY IF EXISTS "Users can view own settings" ON user_entity_settings;
DROP POLICY IF EXISTS "Users can insert own settings" ON user_entity_settings;
DROP POLICY IF EXISTS "Users can update own settings" ON user_entity_settings;
DROP POLICY IF EXISTS "Users can view own alerts" ON alert_history;

-- RLS Policies for users table
CREATE POLICY "Users can view own data" ON users
  FOR SELECT USING (auth.uid() = auth_id);

CREATE POLICY "Users can update own data" ON users
  FOR UPDATE USING (auth.uid() = auth_id);

-- RLS Policies for watchlists table
CREATE POLICY "Users can view own watchlists" ON watchlists
  FOR SELECT USING (
    auth.uid() = (SELECT auth_id FROM users WHERE id = user_id)
  );

CREATE POLICY "Users can insert own watchlists" ON watchlists
  FOR INSERT WITH CHECK (
    auth.uid() = (SELECT auth_id FROM users WHERE id = user_id)
  );

CREATE POLICY "Users can update own watchlists" ON watchlists
  FOR UPDATE USING (
    auth.uid() = (SELECT auth_id FROM users WHERE id = user_id)
  );

CREATE POLICY "Users can delete own watchlists" ON watchlists
  FOR DELETE USING (
    auth.uid() = (SELECT auth_id FROM users WHERE id = user_id)
  );

-- RLS Policies for user_entity_settings table
CREATE POLICY "Users can view own settings" ON user_entity_settings
  FOR SELECT USING (
    auth.uid() = (SELECT auth_id FROM users WHERE id = user_id)
  );

CREATE POLICY "Users can insert own settings" ON user_entity_settings
  FOR INSERT WITH CHECK (
    auth.uid() = (SELECT auth_id FROM users WHERE id = user_id)
  );

CREATE POLICY "Users can update own settings" ON user_entity_settings
  FOR UPDATE USING (
    auth.uid() = (SELECT auth_id FROM users WHERE id = user_id)
  );

-- RLS Policies for alert_history table (read-only for users)
CREATE POLICY "Users can view own alerts" ON alert_history
  FOR SELECT USING (
    auth.uid() = (SELECT auth_id FROM users WHERE id = user_id)
  );

-- Public read access to entities table (everyone can see stock metadata)
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Anyone can view entities" ON entities;
CREATE POLICY "Anyone can view entities" ON entities
  FOR SELECT USING (true);

-- Grant necessary permissions
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON entities TO anon, authenticated;
GRANT SELECT, UPDATE ON users TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON watchlists TO authenticated;
GRANT SELECT, INSERT, UPDATE ON user_entity_settings TO authenticated;
GRANT SELECT ON alert_history TO authenticated;
