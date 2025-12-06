ALTER TABLE "public"."ci_measurements" ADD COLUMN "os_name" text;
ALTER TABLE "public"."ci_measurements" ADD COLUMN "cpu_arch" text;
ALTER TABLE "public"."ci_measurements" ADD COLUMN "job_id" text;
ALTER TABLE "public"."ci_measurements" ADD COLUMN "version" text;

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (capabilities #> '{api,routes}')::jsonb || '["/v3/ci/measurement/add"]',
    true
);