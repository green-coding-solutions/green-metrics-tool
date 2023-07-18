DROP INDEX IF EXISTS stats_project_id, sorting, measurements_project_id, measurements_get, measurements_phase_update, measurements_build_phases, measurements_build_phases2, phase_stats_project_id, notes_project_id, ci_measurements_get, measurements_build_and_store_phase_stats;

CREATE UNIQUE INDEX measurements_get ON measurements(project_id ,metric ,detail_name ,time );
CREATE INDEX measurements_phase_update ON measurements(project_id ,phase ,time );
CREATE INDEX measurements_build_and_store_phase_stats ON measurements(project_id, metric, unit, detail_name);
CREATE INDEX measurements_build_phases ON measurements(metric, unit, detail_name);

CREATE INDEX "phase_stats_project_id" ON "phase_stats" USING HASH ("project_id");

CREATE INDEX "notes_project_id" ON "notes" USING HASH ("project_id");

CREATE INDEX "ci_measurements_get" ON ci_measurements(repo, branch, workflow, run_id, created_at);
