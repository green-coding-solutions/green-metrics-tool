ALTER TABLE jobs
ADD COLUMN IF NOT EXISTS carbon_simulation jsonb NOT NULL DEFAULT '{}';

ALTER TABLE watchlist
ADD COLUMN IF NOT EXISTS carbon_simulation jsonb NOT NULL DEFAULT '{}';
