UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (capabilities->'api'->'routes') || '"\/v2\/timeline"'::jsonb
)
WHERE
    capabilities->'api'->'routes' ? '/v1/timeline'
    AND NOT (capabilities->'api'->'routes' ? '/v2/timeline');