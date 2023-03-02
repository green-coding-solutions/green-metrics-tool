CREATE TABLE machines (
    id SERIAL PRIMARY KEY,
    description text,
    created_at timestamp with time zone DEFAULT now()
);

ALTER TABLE jobs
  ADD COLUMN "machine_id" int DEFAULT NULL,
  ADD CONSTRAINT "machine_id" FOREIGN KEY ("machine_id") REFERENCES "machines"("id") ON DELETE SET NULL ON UPDATE CASCADE;