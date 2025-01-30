UPDATE "public"."users"
SET capabilities = jsonb_set(
    capabilities,
    '{measurement}',
    COALESCE(
        capabilities #> '{measurement}', -- Keep existing orchestrators
        '{}'::jsonb -- Default to empty object if null
    ) ||
    '{"orchestrators":{"docker": {"allow-args": ["--label\\\\s+([\\\\w.-]+)=([\\\\w.-]+)"]}}}'::jsonb
)
WHERE id=1;