UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,playwright_process_duration}',
    'null'::jsonb,
    true
) WHERE capabilities #> '{measurement,playwright_process_duration}' IS NULL;
