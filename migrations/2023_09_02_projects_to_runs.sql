ALTER TABLE projects RENAME TO "runs";
ALTER TABLE runs RENAME COLUMN "invalid_project" TO "invalid_run";

ALTER TABLE measurements RENAME COLUMN "project_id" TO "run_id";
ALTER TABLE phase_stats RENAME COLUMN "project_id" TO "run_id";
ALTER TABLE client_status RENAME COLUMN "project_id" TO "run_id";
ALTER TABLE jobs RENAME COLUMN "project_id" TO "run_id";
ALTER TABLE notes RENAME COLUMN "project_id" TO "run_id";
ALTER TABLE network_intercepts RENAME COLUMN "project_id" TO "run_id";

ALTER TABLE ci_measurements DROP COLUMN "project_id";
