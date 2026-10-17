CREATE TYPE job_type AS ENUM ('email-simple', 'email-report', 'run');

ALTER TABLE jobs
  ALTER COLUMN "type" TYPE job_type USING type::job_type,
  ALTER COLUMN "type" SET NOT NULL;

ALTER TABLE software_tasks
  ALTER COLUMN software_id SET NOT NULL;

ALTER TABLE ci_measurements
  ALTER COLUMN branch SET NOT NULL,
  ALTER COLUMN workflow_id SET NOT NULL;
