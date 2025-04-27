UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (capabilities #> '{api,routes}')::jsonb || '["/v1/user/setting","/v1/user/settings"]',
    true -- Create the key if it doesn't exist
);

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{user,updateable_settings}',
    '["measurement.disabled_metric_providers","measurement.flow_process_duration","measurement.total_duration"]'::jsonb,
    true -- Create the key if it doesn't exist
);