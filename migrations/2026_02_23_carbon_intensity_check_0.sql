ALTER TABLE "ci_measurements" ADD CHECK (carbon_intensity_g > 0);
ALTER TABLE "hog_simplified_measurements" ADD CHECK (carbon_intensity_g > 0);
ALTER TABLE "carbondb_data_raw" ADD CHECK (carbon_intensity_g > 0);
