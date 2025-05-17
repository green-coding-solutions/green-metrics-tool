UPDATE measurements SET value = value * 1000, unit = 'uJ' WHERE unit = 'mJ';

UPDATE phase_stats SET unit = 'uJ', value = value*1000 WHERE unit = 'mJ';

CREATE TABLE measurement_metrics (
    id SERIAL PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE,
    metric text NOT NULL,
    detail_name text NOT NULL,
    unit text NOT NULL
);

CREATE UNIQUE INDEX measurement_metrics_get ON measurement_metrics(run_id,metric,detail_name);
CREATE INDEX measurement_metrics_build_and_store_phase_stats ON measurement_metrics(run_id,metric,detail_name,unit);
CREATE INDEX measurement_metrics_build_phases ON measurement_metrics(metric,detail_name,unit);

CREATE TABLE measurement_values (
    measurement_metric_id int NOT NULL REFERENCES measurement_metrics(id) ON DELETE CASCADE ON UPDATE CASCADE,
    value bigint NOT NULL,
    time bigint NOT NULL
);

CREATE INDEX measurement_values_mmid ON measurement_values(measurement_metric_id);
CREATE UNIQUE INDEX measurement_values_unique ON measurement_values(measurement_metric_id, time);

INSERT INTO measurement_metrics (run_id, metric, detail_name, unit)
SELECT DISTINCT run_id, metric, detail_name, unit
FROM measurements;

INSERT INTO measurement_values (measurement_metric_id, value, time)
SELECT
    mm.id AS measurement_metric_id,
    m.value,
    m.time
FROM
    measurements m
JOIN
    measurement_metrics mm
ON
    m.run_id = mm.run_id
    AND m.metric = mm.metric
    AND m.detail_name = mm.detail_name
    AND m.unit = mm.unit;

DROP TABLE measurements;

ALTER TABLE phase_stats
    ADD COLUMN "sampling_rate_avg" int,
    ADD COLUMN "sampling_rate_max" int,
    ADD COLUMN "sampling_rate_95p" int;

UPDATE phase_stats SET sampling_rate_avg = 0, sampling_rate_max = 0, sampling_rate_95p = 0;

ALTER TABLE "public"."phase_stats"
    ALTER COLUMN "sampling_rate_avg" SET NOT NULL,
    ALTER COLUMN "sampling_rate_max" SET NOT NULL,
    ALTER COLUMN "sampling_rate_95p" SET NOT NULL;
