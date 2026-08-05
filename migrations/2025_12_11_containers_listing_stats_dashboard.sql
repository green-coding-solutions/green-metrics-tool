ALTER TABLE "runs" ADD COLUMN "containers" jsonb;
ALTER TABLE "runs" RENAME COLUMN "usage_scenario_dependencies" TO "container_dependencies";
