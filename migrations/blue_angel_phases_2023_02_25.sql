ALTER TABLE "projects" ADD COLUMN "phases" JSON DEFAULT NULL;

ALTER TABLE "stats" ADD COLUMN "phase" text DEFAULT NULL;

CREATE TABLE phase_stats (
    id SERIAL PRIMARY KEY,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE,
    metric text,
    detail_name text,
    phase text,
    value bigint,
    unit text,
    created_at timestamp with time zone DEFAULT now()
);
