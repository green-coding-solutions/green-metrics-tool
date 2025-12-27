DROP INDEX "ip_data_pkey";

ALTER TABLE "ip_data"
  ADD COLUMN "id" serial,
  ADD PRIMARY KEY ("id");

UPDATE ci_measurements SET lat = NULL WHERE lat = '';
UPDATE ci_measurements SET lon = NULL WHERE lon = '';

ALTER TABLE "ci_measurements"
  ALTER COLUMN "lat" TYPE DOUBLE PRECISION USING lat::DOUBLE PRECISION,
  ALTER COLUMN "lon" TYPE DOUBLE PRECISION USING lon::DOUBLE PRECISION,
  RENAME COLUMN "lat" TO "latitude",
  RENAME COLUMN "lon" TO "longitude";

ALTER TABLE "public"."ip_data"
  ADD COLUMN "latitude" DOUBLE PRECISION ,
  ADD COLUMN "longitude" DOUBLE PRECISION,
  ADD COLUMN "city" text,
  ADD COLUMN "zip" text,
  ADD COLUMN "org" text,
  ADD COLUMN "country_code" text;

UPDATE ip_data
SET
    latitude = (data->>'lat')::DOUBLE PRECISION,
    longitude = (data->>'lon')::DOUBLE PRECISION,
    city = (data->>'city'),
    org = (data->>'org'),
    zip = (data->>'zip'),
    country_code = (data->>'countryCode')
    WHERE longitude IS NULL;

UPDATE ip_data
SET
    latitude = (data->>'latitude')::DOUBLE PRECISION,
    longitude = (data->>'longitude')::DOUBLE PRECISION,
    city = (data->>'city'),
    org = (data->>'org'),
    zip = (data->>'postal'),
    country_code = (data->>'country_code')
    WHERE longitude IS NULL;


ALTER TABLE "ip_data"
  DROP COLUMN "data",
  ALTER COLUMN "latitude" SET NOT NULL,
  ALTER COLUMN "longitude" SET NOT NULL,
  ALTER COLUMN "city" SET NOT NULL,
  ALTER COLUMN "zip" SET NOT NULL,
  ALTER COLUMN "org" SET NOT NULL,
  ALTER COLUMN "country_code" SET NOT NULL;

ALTER TABLE "hog_simplified_measurements"
    ADD COLUMN "ip_address" inet,
    ADD COLUMN latitude DOUBLE PRECISION,
    ADD COLUMN longitude DOUBLE PRECISION;

ALTER TABLE "carbondb_data_raw"
    ADD COLUMN "ip_address" inet,
    ADD COLUMN latitude DOUBLE PRECISION,
    ADD COLUMN longitude DOUBLE PRECISION;

