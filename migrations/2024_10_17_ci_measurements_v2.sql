ALTER TABLE "public"."ci_measurements" RENAME COLUMN "energy_value" TO "energy_uj";
ALTER TABLE "public"."ci_measurements" RENAME COLUMN "co2i" TO "carbon_intensity_g";
ALTER TABLE "public"."ci_measurements" RENAME COLUMN "co2" TO "carbon_ug";
ALTER TABLE "public"."ci_measurements" RENAME COLUMN "duration" TO "duration_us";

ALTER TABLE "public"."ci_measurements"
  DROP COLUMN "energy_unit",
  ADD COLUMN  "ip_address" INET,
  ADD COLUMN "filter_type" text,
  ADD COLUMN "filter_project" text,
  ADD COLUMN "filter_machine" text,
  ADD COLUMN "filter_tags" text[];

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "carbon_intensity_g" TYPE int USING "carbon_intensity_g"::int;

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "carbon_ug" TYPE DOUBLE PRECISION USING "carbon_ug"::DOUBLE PRECISION;

UPDATE ci_measurements SET carbon_ug = carbon_ug*1000000;

UPDATE ci_measurements SET duration_us = duration_us*1000000;


ALTER TABLE "public"."ci_measurements" ALTER COLUMN "carbon_ug" TYPE BIGINT USING "carbon_ug"::BIGINT;

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "user_id" SET NOT NULL;
ALTER TABLE "public"."timeline_projects" ALTER COLUMN "user_id" SET NOT NULL;
ALTER TABLE "public"."hog_measurements" ALTER COLUMN "user_id" SET NOT NULL;


UPDATE ci_measurements SET filter_type = 'machine.ci' WHERE filter_type IS NULL;
UPDATE ci_measurements SET filter_project = 'CI/CD' WHERE filter_project IS NULL;
UPDATE ci_measurements SET filter_machine = 'unknown' WHERE filter_machine IS NULL;
UPDATE ci_measurements SET filter_tags = '{}' WHERE filter_tags IS NULL;

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "filter_type" SET NOT NULL;
ALTER TABLE "public"."ci_measurements" ALTER COLUMN "filter_project" SET NOT NULL;
ALTER TABLE "public"."ci_measurements" ALTER COLUMN "filter_machine" SET NOT NULL;
ALTER TABLE "public"."ci_measurements" ALTER COLUMN "filter_tags" SET NOT NULL;


CREATE VIEW carbondb_data_view AS
SELECT cd.*, t.type as type_str, s.source as source_str, m.machine as machine_str, p.project as project_str FROM carbondb_data as cd
LEFT JOIN carbondb_types as t ON cd.type = t.id
LEFT JOIN carbondb_sources as s ON cd.source = s.id
LEFT JOIN carbondb_machines as m ON cd.machine = m.id
LEFT JOIN carbondb_projects as p ON cd.project = p.id;

UPDATE phase_stats
SET metric = REPLACE(metric, '_co2_', '_carbon_')
WHERE metric LIKE '%_co2_%';
