UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{user,updateable_settings}',
    (
        COALESCE(capabilities->'user'->'updateable_settings', '[]'::jsonb) ||
        '["measurement.system_check_threshold", "measurement.pre_test_sleep", "measurement.idle_duration", "measurement.baseline_duration", "measurement.post_test_sleep", "measurement.phase_transition_time", "measurement.wait_time_dependencies"]'::jsonb
    ),
    true
) WHERE id != 0;

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,system_check_threshold}',
   '3',
    true
);

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,pre_test_sleep}',
   '5',
    true
);

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,idle_duration}',
    '60',
    true
);

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,baseline_duration}',
    '60',
    true
);

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,post_test_sleep}',
   '5',
    true
);

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,phase_transition_time}',
   '1',
    true
);

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,wait_time_dependencies}',
    '60',
    true
);

