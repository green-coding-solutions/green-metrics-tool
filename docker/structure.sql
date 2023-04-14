CREATE DATABASE "green-coding";
\c green-coding;

CREATE EXTENSION "uuid-ossp";

CREATE TABLE projects (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    name text,
    uri text,
    branch text,
    email text,
    categories int[],
    usage_scenario json,
    machine_specs jsonb,
    measurement_config jsonb,
    start_measurement bigint,
    end_measurement bigint,
    invalid_project text,
    last_run timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE stats (
    id SERIAL PRIMARY KEY,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE,
    detail_name text,
    metric text,
    value bigint,
    unit text,
    time bigint,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name text,
    parent_id int REFERENCES categories(id) ON DELETE CASCADE ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE machines (
    id SERIAL PRIMARY KEY,
    description text,
    created_at timestamp with time zone DEFAULT now()
);


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
    label text,
    source text,
    project_id uuid REFERENCES projects(id) ON DELETE SET NULL ON UPDATE CASCADE DEFAULT null,
    created_at timestamp with time zone DEFAULT now()
);
