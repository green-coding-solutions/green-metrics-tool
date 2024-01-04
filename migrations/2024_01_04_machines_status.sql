ALTER TABLE "machines" ADD COLUMN "gmt_hash" text;
ALTER TABLE "machines" ADD COLUMN "gmt_timestamp" timestamp with time zone;
ALTER TABLE "machines" ADD COLUMN "jobs_processing" text;
