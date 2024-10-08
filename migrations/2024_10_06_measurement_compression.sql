CREATE TABLE measurement_metrics (
    id SERIAL PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE,
    metric text NOT NULL,
    detail_name text NOT NULL,
    unit text NOT NULL
);

-- Indices -------------------------------------------------------

CREATE INDEX idx_measurement_metrics_build_and_store_phase_stats ON measurement_metrics(run_id uuid_ops,metric text_ops,detail_name text_ops, unit text_ops);
CREATE INDEX idx_measurement_metrics_build_phases ON measurement_metrics(metric text_ops,unit text_ops,detail_name text_ops);
CREATE UNIQUE INDEX idx_measurements_get ON measurement_metrics(run_id uuid_ops,metric text_ops,detail_name text_ops); -- unit omitted, as we do not want to have two metrics with different units

INSERT INTO measurement_metrics (run_id, metric, detail_name, unit)
SELECT run_id, metric, detail_name, unit
FROM measurements
GROUP BY run_id, metric, detail_name, unit; -- Takes 647 s

CREATE TABLE measurement_values (
    measurement_metric_id int NOT NULL REFERENCES measurement_metrics(id) ON DELETE CASCADE ON UPDATE CASCADE,
    value bigint NOT NULL,
    time bigint NOT NULL
);


INSERT INTO measurement_values (measurement_metric_id, value, time)
SELECT a.id, b.value, b.time
FROM measurement_metrics as a
LEFT JOIN measurements as b ON a.run_id = b.run_id AND a.metric = b.metric AND a.detail_name = b.detail_name AND a.unit = b.unit;  -- Takes 4589 s

