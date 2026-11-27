-- Optimizations are now opt-in. measurement.skip_optimizations is replaced by measurement.optimizations (default: false)

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{user,updateable_settings}',
    (SELECT jsonb_agg(
        CASE WHEN elem = '"measurement.skip_optimizations"'::jsonb THEN '"measurement.optimizations"'::jsonb ELSE elem END
     )
     FROM jsonb_array_elements(capabilities->'user'->'updateable_settings') elem)
)
WHERE capabilities->'user'->'updateable_settings' @> '"measurement.skip_optimizations"'::jsonb;

UPDATE users
SET capabilities = jsonb_set(
    capabilities #- '{measurement,skip_optimizations}',
    '{measurement,optimizations}',
    'false',
    true
)
WHERE capabilities ? 'measurement';
