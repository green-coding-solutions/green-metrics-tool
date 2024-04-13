ALTER TABLE "jobs"
  ALTER COLUMN "machine_id" DROP NOT NULL,
  ALTER COLUMN "filename" DROP NOT NULL,
  ALTER COLUMN "branch" DROP NOT NULL,
  ADD COLUMN "type" text,
  ADD COLUMN "message" text;
