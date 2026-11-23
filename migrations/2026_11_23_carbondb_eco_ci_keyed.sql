-- Eco CI rows in carbondb_data_raw are now keyed on their source measurement, so the copy over can skip
-- already copied rows instead of inserting the whole lookback window again on every run.
ALTER TABLE carbondb_data_raw ADD COLUMN ci_measurement_id integer; -- only set for Eco CI. No FK as data must persist in CarbonDB when measurements are deleted
CREATE UNIQUE INDEX carbondb_data_raw_ci_measurement_id_unique ON carbondb_data_raw (ci_measurement_id); -- NULLs are distinct, so only Eco CI rows are constrained

-- Existing Eco CI rows in carbondb_data_raw have no ci_measurement_id yet. Until they leave the copy over window the copy over
-- inserts them again and remove_duplicates has to delete the old rows. Run tools/rebuild_carbondb.py once after this migration
-- to re-copy all Eco CI data with ci_measurement_id set.
