ALTER TABLE "runs" ADD COLUMN "usage_scenario_variables" jsonb NOT NULL DEFAULT '{}';

ALTER TABLE "jobs" ADD COLUMN "usage_scenario_variables" jsonb NOT NULL DEFAULT '{}';

ALTER TABLE "watchlist" ADD COLUMN "usage_scenario_variables" jsonb NOT NULL DEFAULT '{}';


UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (capabilities #> '{api,routes}')::jsonb || '["/v2/jobs","/v2/runs","/v2/run/{run_id}"]',
    true -- Create the key if it doesn't exist
);