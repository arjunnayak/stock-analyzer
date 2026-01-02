-- Migration 004: Add template alert tracking
-- Adds last_alerted_templates column to track when each template last sent an alert

-- Add last_alerted_templates column to user_entity_settings
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'user_entity_settings'
      AND column_name = 'last_alerted_templates'
  ) THEN
    ALTER TABLE user_entity_settings
    ADD COLUMN last_alerted_templates JSONB DEFAULT '{}'::jsonb;
  END IF;
END $$;

-- Create index for efficient user_id + entity_id lookups
CREATE INDEX IF NOT EXISTS idx_user_entity_settings_lookup
ON user_entity_settings(user_id, entity_id);

-- Add comment for documentation
COMMENT ON COLUMN user_entity_settings.last_alerted_templates IS
'Tracks last alert date per template ID. Format: {"T1": "2024-12-20", "T5": "2024-12-22"}. Used for 7-day deduplication window.';
