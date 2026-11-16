UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (capabilities->'api'->'routes') || '"/v1/logs/{run_id}"'::jsonb
)
WHERE capabilities->'api'->'routes' ? '/v2/run/{run_id}'
    AND NOT (capabilities->'api'->'routes' ? '/v1/logs/{run_id}');
