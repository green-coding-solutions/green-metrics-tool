CREATE TABLE network_intercepts (
    id SERIAL PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE ,
    time bigint NOT NULL,
    connection_type text NOT NULL,
    protocol text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);