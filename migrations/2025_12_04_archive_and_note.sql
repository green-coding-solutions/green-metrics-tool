ALTER TABLE "runs" ADD COLUMN "archived" bool DEFAULT 'FALSE';
ALTER TABLE "runs" ADD COLUMN "note" text NOT NULL DEFAULT '';

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    coalesce(capabilities->'api'->'routes', '[]'::jsonb) || '["/v1/run/{run_id}"]'::jsonb
)
WHERE id != 0;