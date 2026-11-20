-- Eco CI now transmits operational and embodied carbon separately (/v4/ci/measurement/add)
ALTER TABLE "public"."ci_measurements" ADD COLUMN "operational_carbon_ug" bigint;
ALTER TABLE "public"."ci_measurements" ADD COLUMN "embodied_carbon_ug" bigint;

-- Split the historic combined carbon_ug. Same logic as api/eco_ci.py::split_carbon_ug
-- Eco CI only sent carbon_ug together with carbon_intensity_g, so the operational part can be recalculated
UPDATE ci_measurements
SET
    operational_carbon_ug = ROUND(energy_uj::DOUBLE PRECISION * carbon_intensity_g / 3600000),
    embodied_carbon_ug = GREATEST(carbon_ug - ROUND(energy_uj::DOUBLE PRECISION * carbon_intensity_g / 3600000), 0)
WHERE carbon_ug IS NOT NULL AND carbon_intensity_g IS NOT NULL
    AND operational_carbon_ug IS NULL AND embodied_carbon_ug IS NULL; -- never overwrite values a client reported split up

-- Without a carbon intensity no operational carbon can have been calculated, so the value can only be embodied
UPDATE ci_measurements
SET embodied_carbon_ug = carbon_ug
WHERE carbon_ug IS NOT NULL AND carbon_intensity_g IS NULL
    AND operational_carbon_ug IS NULL AND embodied_carbon_ug IS NULL; -- never overwrite values a client reported split up

ALTER TABLE "public"."ci_measurements" DROP COLUMN "carbon_ug";

-- /v2/ci/measurement/add is removed, /v4/ci/measurement/add is added
UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    ((capabilities #> '{api,routes}')::jsonb - '/v2/ci/measurement/add') || '["/v4/ci/measurement/add"]',
    true
)
WHERE capabilities #> '{api,routes}' ?| array['/v2/ci/measurement/add', '/v3/ci/measurement/add']; -- only users that were allowed to add CI data before

-- /v1/ci/measurements is deprecated (returns 410) as its returned data changed. /v2/ci/measurements replaces it
UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (capabilities #> '{api,routes}')::jsonb || '["/v2/ci/measurements"]',
    true
)
WHERE capabilities #> '{api,routes}' ? '/v1/ci/measurements'
    AND NOT capabilities #> '{api,routes}' ? '/v2/ci/measurements';

