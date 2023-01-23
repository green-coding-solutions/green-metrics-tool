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
    usage_scenario jsonb,
    machine_specs jsonb,
    measurement_config jsonb,
    start_measurement bigint,
    end_measurement bigint,
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


CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE DEFAULT null,
    type text,
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
