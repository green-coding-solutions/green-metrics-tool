ALTER TABLE "public"."ci_measurements" RENAME COLUMN "energy_value" TO "energy_uj";
ALTER TABLE "public"."ci_measurements"
  DROP COLUMN "energy_unit",
  ADD COLUMN "filter_type" text,
  ADD COLUMN "filter_project" text,
  ADD COLUMN "filter_machine" text,
  ADD COLUMN "filter_tags" text[];

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "user_id" SET NOT NULL;
ALTER TABLE "public"."timeline_projects" ALTER COLUMN "user_id" SET NOT NULL;
ALTER TABLE "public"."hog_measurements" ALTER COLUMN "user_id" SET NOT NULL;
