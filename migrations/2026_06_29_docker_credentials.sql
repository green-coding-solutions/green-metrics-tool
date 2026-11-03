ALTER TABLE users
ADD COLUMN IF NOT EXISTS docker_credentials text;

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{user,updateable_settings}',
    (
        COALESCE(capabilities->'user'->'updateable_settings', '[]'::jsonb) ||
        '["docker_credentials"]'::jsonb
    ),
    true
) WHERE id != 0;
