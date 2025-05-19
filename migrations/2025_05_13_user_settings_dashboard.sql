UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{user,updateable_settings}',
    (
        COALESCE(capabilities->'user'->'updateable_settings', '[]'::jsonb) ||
        '["measurement.dev_no_sleeps","measurement.dev_no_optimizations"]'::jsonb
    ),
    true
)
WHERE id = 1;


UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,dev_no_sleeps}',
    'false'::jsonb,
    true
)
WHERE id = 1;

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,dev_no_optimizations}',
    'false'::jsonb,
    true
)
WHERE id = 1;