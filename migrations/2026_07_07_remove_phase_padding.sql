UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{user,updateable_settings}',
    (SELECT jsonb_agg(elem)
     FROM jsonb_array_elements(capabilities->'user'->'updateable_settings') elem
     WHERE elem != '"measurement.phase_padding"'::jsonb)
)
WHERE capabilities->'user'->'updateable_settings' @> '"measurement.phase_padding"'::jsonb;

UPDATE users
SET capabilities = capabilities #- '{measurement,phase_padding}'
WHERE (capabilities->'measurement') ? 'phase_padding';
