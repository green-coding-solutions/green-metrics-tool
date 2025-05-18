UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,phase_padding}',
    'true'::jsonb,
    true
); -- for all users

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{user,updateable_settings}',
    (
        COALESCE(capabilities->'user'->'updateable_settings', '[]'::jsonb) ||
        '["measurement.phase_padding"]'::jsonb
    ),
    true
); -- for all users