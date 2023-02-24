CREATE TABLE badges (
    id SERIAL PRIMARY KEY,
    value text,
    repo text,
    branch text,
    workflow text,
    run_id text,
    project_id uuid,
    created_at timestamp with time zone DEFAULT now()
);