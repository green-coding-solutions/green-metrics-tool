-- gen_random_uuid() is built into PostgreSQL since v13, so the uuid-ossp extension is not needed anymore
ALTER TABLE runs ALTER COLUMN id SET DEFAULT gen_random_uuid();
-- No CASCADE on purpose: fails if anything still depends on uuid-ossp instead of silently dropping it
DROP EXTENSION IF EXISTS "uuid-ossp";
