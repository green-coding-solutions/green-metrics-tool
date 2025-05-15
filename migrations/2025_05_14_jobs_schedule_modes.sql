UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{jobs,schedule_modes}',
    (
        COALESCE(capabilities->'jobs'->'schedule_modes', '[]'::jsonb) ||
        '["statistical-significance"]'::jsonb
    ),
    true
)
WHERE id = 1;
