UPDATE users
SET capabilities = capabilities #- '{measurement,allow_unsafe}'
WHERE capabilities #> '{measurement,allow_unsafe}' IS NOT NULL;


UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{measurement,allowed_volume_mounts}',
   '[]',
    true
) WHERE id != 0;
