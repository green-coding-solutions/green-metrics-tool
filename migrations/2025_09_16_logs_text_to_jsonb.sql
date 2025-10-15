-- Migration: Convert logs column from text to jsonb
-- This migration converts the logs column in the runs table from text to jsonb
-- to support structured JSON log data instead of plain text.

-- Step 1: Add a temporary jsonb column
ALTER TABLE runs ADD COLUMN logs_jsonb jsonb;

-- Step 2: Convert existing text logs to jsonb
-- Convert all text logs to new JSON format structure
UPDATE runs
SET logs_jsonb = CASE
    WHEN logs IS NULL OR logs = '' THEN NULL
    -- Convert all logs (text) to the new JSON format structure
    ELSE jsonb_build_object('unified (legacy)', jsonb_build_array(
        jsonb_build_object(
            'type', 'legacy',
            'id', null,
            'cmd', null,
            'phase', null,
            'stdout', logs
        )
    ))
END
WHERE logs IS NOT NULL;

-- Step 3: Drop the old text column
ALTER TABLE runs DROP COLUMN logs;

-- Step 4: Rename the new jsonb column to logs
ALTER TABLE runs RENAME COLUMN logs_jsonb TO logs;
