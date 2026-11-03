ALTER TABLE machines ADD COLUMN IF NOT EXISTS needs_revalidation boolean NOT NULL DEFAULT false;
