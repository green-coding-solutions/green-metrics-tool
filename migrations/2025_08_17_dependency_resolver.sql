-- Add usage_scenario_dependencies column to store dependency resolver output
-- This column will store aggregated JSON output from dependency resolver executions

ALTER TABLE "runs" ADD COLUMN "usage_scenario_dependencies" jsonb NOT NULL DEFAULT '{}';
ALTER TABLE "jobs" ADD COLUMN "usage_scenario_dependencies" jsonb NOT NULL DEFAULT '{}';
ALTER TABLE "watchlist" ADD COLUMN "usage_scenario_dependencies" jsonb NOT NULL DEFAULT '{}';
