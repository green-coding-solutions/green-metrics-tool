ALTER TABLE carbondb_data_raw ADD COLUMN IF NOT EXISTS run_id uuid;

-- Assign existing ScenarioRunner rows to their run. time and user_id are copied verbatim from the run, machine is not used as the description may have changed since
UPDATE carbondb_data_raw AS cdr
SET run_id = r.id
FROM runs AS r
WHERE
    cdr.source = 'ScenarioRunner'
    AND cdr.run_id IS NULL
    AND cdr.time = EXTRACT(EPOCH FROM r.created_at) * 1e6
    AND cdr.user_id = r.user_id;

-- Rows of the same run that differ in energy_kwh / carbon_kg survived remove_duplicates and were counted multiple times.
-- Keep only the latest copy, as it carries the most recent values
DELETE FROM carbondb_data_raw a
USING carbondb_data_raw b
WHERE
    a.run_id = b.run_id
    AND a.id < b.id;

CREATE UNIQUE INDEX IF NOT EXISTS carbondb_data_raw_run_id_unique ON carbondb_data_raw (run_id);

-- carbondb_data is re-aggregated for the last days by the next run of cron/carbondb_compress.py
