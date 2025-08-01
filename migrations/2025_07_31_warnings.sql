CREATE TABLE warnings (
    id SERIAL PRIMARY KEY,
    run_id uuid REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE,
    message text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE INDEX "warnings_run_id" ON "warnings" USING HASH ("run_id");
CREATE TRIGGER warnings_moddatetime
    BEFORE UPDATE ON warnings
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (
        COALESCE(capabilities->'api'->'routes', '[]'::jsonb) ||
        '["/v1/warnings/{run_id}"]'::jsonb
    ),
    true
)
WHERE id != 0