ALTER TABLE "public"."carbondb_data_raw"
  ALTER COLUMN "carbon_intensity_g" DROP NOT NULL,
  ALTER COLUMN "carbon_kg" DROP NOT NULL;
