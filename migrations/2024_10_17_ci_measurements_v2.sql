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
  ADD COLUMN "filter_tags" text[],
  ADD COLUMN "filter_source" text DEFAULT 'Eco-CI'; -- add static column because we do not allow inserts from other source atm

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "carbon_intensity_g" TYPE int USING "carbon_intensity_g"::int;

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "carbon_ug" TYPE DOUBLE PRECISION USING "carbon_ug"::DOUBLE PRECISION;

UPDATE ci_measurements SET carbon_ug = carbon_ug*1000000;

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "carbon_ug" TYPE BIGINT USING "carbon_ug"::BIGINT;

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "user_id" SET NOT NULL;
ALTER TABLE "public"."timeline_projects" ALTER COLUMN "user_id" SET NOT NULL;
ALTER TABLE "public"."hog_measurements" ALTER COLUMN "user_id" SET NOT NULL;
