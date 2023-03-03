CREATE TABLE badges (
    id SERIAL PRIMARY KEY,
    value bigint,
    unit text,
    repo text,
    branch text,
    workflow text,
    run_id text,
    project_id uuid REFERENCES projects(id) ON DELETE SET NULL ON UPDATE CASCADE DEFAULT null,
    created_at timestamp with time zone DEFAULT now()
);