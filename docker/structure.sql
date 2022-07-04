CREATE DATABASE "green-coding";
\c green-coding;

CREATE EXTENSION "uuid-ossp";

CREATE TABLE projects (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    name text,
    url text,
    email text,
    usage_scenario jsonb,
    cpu text,
    memtotal text,
    crawled boolean DEFAULT false,
    last_crawl timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE stats (
    id SERIAL PRIMARY KEY,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE,
    container_name text,
    metric text,
    value bigint,
    time bigint,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE DEFAULT null,
    type text,
    failed boolean DEFAULT false,
    running boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE notes (
    id SERIAL PRIMARY KEY,
    project_id uuid REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE,
    container_name text,
    note text,
    time bigint,
    created_at timestamp with time zone DEFAULT now()
);
