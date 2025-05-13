UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{user,updateable_settings}',
    '["measurement.dev_no_sleeps","measurement.dev_no_optimizations","measurement.total_duration"]'::jsonb,
    true -- Create the key if it doesn't exist
)
WHERE user_id = 1;