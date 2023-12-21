UPDATE runs SET filename = 'usage_scenario.yml' WHERE filename IS NULL;
UPDATE jobs SET filename = 'usage_scenario.yml' WHERE filename IS NULL;
UPDATE timeline_projects SET filename = 'usage_scenario.yml' WHERE filename IS NULL;

UPDATE runs SET branch = 'main' WHERE branch IS NULL;
UPDATE jobs SET branch = 'main' WHERE branch IS NULL;
UPDATE timeline_projects SET branch = 'main' WHERE branch IS NULL;


ALTER TABLE "public"."jobs"
  ALTER COLUMN "branch" DROP DEFAULT,
  ALTER COLUMN "branch" SET NOT NULL,
  ALTER COLUMN "filename" DROP DEFAULT,
  ALTER COLUMN "filename" SET NOT NULL;

ALTER TABLE "public"."timeline_projects"
  ALTER COLUMN "branch" DROP DEFAULT,
  ALTER COLUMN "branch" SET NOT NULL,
  ALTER COLUMN "filename" DROP DEFAULT,
  ALTER COLUMN "filename" SET NOT NULL;

ALTER TABLE "public"."runs"
  ALTER COLUMN "branch" DROP DEFAULT,
  ALTER COLUMN "branch" SET NOT NULL,
  ALTER COLUMN "filename" DROP DEFAULT,
  ALTER COLUMN "filename" SET NOT NULL;