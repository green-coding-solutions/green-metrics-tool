CREATE INDEX "stats_project_id" ON "measurements" USING HASH ("project_id");
CREATE INDEX sorting ON measurements (metric, detail_name, time);
