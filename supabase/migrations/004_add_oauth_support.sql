-- Migration: Add OAuth support
-- Adds name column to users table and updates trigger to extract name from OAuth metadata

-- Add name column to users table for storing display name from OAuth providers
ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT;

-- Update the handle_new_user function to extract name from OAuth metadata
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
  user_name TEXT;
BEGIN
  -- Extract name from OAuth metadata if available (Google, GitHub, etc.)
  user_name := COALESCE(
    NEW.raw_user_meta_data->>'full_name',
    NEW.raw_user_meta_data->>'name',
    NEW.raw_user_meta_data->>'user_name'
  );

  INSERT INTO public.users (auth_id, email, name, created_at, updated_at, alerts_enabled)
  VALUES (NEW.id, NEW.email, user_name, NOW(), NOW(), TRUE)
  ON CONFLICT (auth_id) DO UPDATE SET
    name = COALESCE(EXCLUDED.name, users.name),
    updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
