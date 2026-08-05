ALTER TABLE "ci_measurements" ADD CONSTRAINT ci_measurements_carbon_intensity_check CHECK (carbon_intensity_g > 0);
ALTER TABLE "hog_simplified_measurements" ADD CONSTRAINT hog_measurements_carbon_intensity_check CHECK (carbon_intensity_g > 0);
ALTER TABLE "carbondb_data_raw" ADD CONSTRAINT carbondb_raw_carbon_intensity_check CHECK (carbon_intensity_g > 0);