CREATE DATABASE "green-coding";
\c green-coding;

CREATE EXTENSION "uuid-ossp";

CREATE TABLE projects (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    name text,
    uri text,
    branch text,
    commit_hash text,
    email text,
    categories int[],
    usage_scenario json,
    filename text,
    machine_specs jsonb,
    machine_id int DEFAULT 1,
    measurement_config jsonb,
    start_measurement bigint,
    end_measurement bigint,
    phases JSON DEFAULT null,
    invalid_project text,
    last_run timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE measurements (
    id SERIAL PRIMARY KEY,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE,
    detail_name text,
    metric text,
    value bigint,
    unit text,
    time bigint,
    phase text DEFAULT null,
    created_at timestamp with time zone DEFAULT now()
);

CREATE INDEX "stats_project_id" ON "measurements" USING HASH ("project_id");
CREATE INDEX sorting ON measurements (metric, detail_name, time);


CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name text,
    parent_id int REFERENCES categories(id) ON DELETE CASCADE ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE machines (
    id SERIAL PRIMARY KEY,
    description text,
    available boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT NULL
);

CREATE TABLE phase_stats (
    id SERIAL PRIMARY KEY,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE,
    metric text,
    detail_name text,
    phase text,
    value bigint,
    type text,
    max_value bigint DEFAULT NULL,
    unit text,
    created_at timestamp with time zone DEFAULT now()
);
CREATE UNIQUE INDEX description_unique ON machines(description text_ops);


CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE DEFAULT null,
    type text,
    machine_id int REFERENCES machines(id) ON DELETE SET NULL ON UPDATE CASCADE DEFAULT null,
    failed boolean DEFAULT false,
    running boolean DEFAULT false,
    last_run timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE notes (
    id SERIAL PRIMARY KEY,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE,
    detail_name text,
    note text,
    time bigint,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE ci_measurements (
    id SERIAL PRIMARY KEY,
    value bigint,
    unit text,
    repo text,
    branch text,
    workflow text,
    run_id text,
    cpu text DEFAULT NULL,
    commit_hash text DEFAULT NULL,
    label text,
    source text,
    project_id uuid REFERENCES projects(id) ON DELETE SET NULL ON UPDATE CASCADE DEFAULT null,
    created_at timestamp with time zone DEFAULT now()
);
