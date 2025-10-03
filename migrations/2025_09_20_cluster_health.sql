ALTER TABLE "changelog" RENAME TO "cluster_changelog";

CREATE TABLE cluster_status_messages (
    id SERIAL PRIMARY KEY,
    message text,
    resolved boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE TRIGGER cluster_status_messages_moddatetime
    BEFORE UPDATE ON cluster_status_messages
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    coalesce(capabilities->'api'->'routes', '[]'::jsonb) || '["/v1/cluster/status"]'::jsonb
)
WHERE id != 0;

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    coalesce(capabilities->'api'->'routes', '[]'::jsonb) || '["/v1/cluster/status/history"]'::jsonb
)
WHERE id != 0;

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    coalesce(capabilities->'api'->'routes', '[]'::jsonb) || '["/v1/cluster/changelog"]'::jsonb
)
WHERE id != 0;