-- CarbonDB also stores operational and embodied carbon separately
-- carbon_kg of CUSTOM data has always been only operational carbon (energy * carbon intensity), so the rename is correct for it.
-- Eco CI, ScenarioRunner and Power HOG data contained embodied carbon in it and must be rebuilt from their source tables.
-- !!! Run tools/rebuild_carbondb.py once after this migration !!!
ALTER TABLE "public"."carbondb_data_raw" RENAME COLUMN "carbon_kg" TO "operational_carbon_kg";
-- historic CUSTOM data had no embodied carbon. All other sources are re-copied by tools/rebuild_carbondb.py
ALTER TABLE "public"."carbondb_data_raw" ADD COLUMN "embodied_carbon_kg" DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE "public"."carbondb_data_raw" ALTER COLUMN "embodied_carbon_kg" DROP DEFAULT;

ALTER TABLE "public"."carbondb_data" RENAME COLUMN "carbon_kg_sum" TO "operational_carbon_kg_sum";
ALTER TABLE "public"."carbondb_data" ADD COLUMN "embodied_carbon_kg_sum" DOUBLE PRECISION NOT NULL DEFAULT 0;
ALTER TABLE "public"."carbondb_data" ALTER COLUMN "embodied_carbon_kg_sum" DROP DEFAULT;

-- /v2/carbondb/add is removed, /v3/carbondb/add requires embodied carbon
UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    ((capabilities #> '{api,routes}')::jsonb - '/v2/carbondb/add') || '["/v3/carbondb/add"]',
    true
)
WHERE capabilities #> '{api,routes}' ? '/v2/carbondb/add'; -- only users that were allowed to add data before

-- views expand cd.* at creation time, so the renamed and added columns need a re-creation
DROP VIEW IF EXISTS carbondb_data_view;
CREATE VIEW carbondb_data_view AS
SELECT cd.*, t.type as type_str, s.source as source_str, m.machine as machine_str, p.project as project_str FROM carbondb_data as cd
LEFT JOIN carbondb_types as t ON cd.type = t.id
LEFT JOIN carbondb_sources as s ON cd.source = s.id
LEFT JOIN carbondb_machines as m ON cd.machine = m.id
LEFT JOIN carbondb_projects as p ON cd.project = p.id;