CREATE TABLE system_logs (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title text NOT NULL,
    message text NOT NULL,
    level text NOT NULL DEFAULT 'error',
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE TRIGGER system_logs_moddatetime
    BEFORE UPDATE ON system_logs
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE INDEX system_logs_created_at_idx
    ON system_logs (created_at DESC, id DESC);

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (capabilities->'api'->'routes') || '"/v1/system-logs"'::jsonb || '"/v1/system-log"'::jsonb
)
WHERE id = 1
    AND NOT (capabilities->'api'->'routes' ? '/v1/system-logs');
