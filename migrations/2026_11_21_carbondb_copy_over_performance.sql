-- Power HOG rows in carbondb_data_raw are now keyed on their source measurement, so the copy over can skip
-- already copied rows instead of inserting the whole lookback window again on every run.
ALTER TABLE carbondb_data_raw ADD COLUMN hog_measurement_id bigint; -- only set for Power HOG. No FK as data must persist in CarbonDB when measurements are deleted
CREATE UNIQUE INDEX carbondb_data_raw_hog_measurement_id_unique ON carbondb_data_raw (hog_measurement_id); -- NULLs are distinct, so only Power HOG rows are constrained

-- copy over to CarbonDB filters ci_measurements on created_at only. The existing index has created_at only as last column
CREATE INDEX ci_measurements_created_at ON ci_measurements(created_at);

-- Existing Power HOG rows in carbondb_data_raw have no hog_measurement_id yet. Until they are replaced the copy over
-- inserts them again and remove_duplicates has to delete the old rows. Run tools/rebuild_carbondb.py once after this migration
-- to re-copy all Power HOG data with hog_measurement_id set.
