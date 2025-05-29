UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (
        COALESCE(capabilities->'api'->'routes', '[]'::jsonb) ||
        '["/v1/job"]'::jsonb
    ),
    true
)
WHERE id = 1;