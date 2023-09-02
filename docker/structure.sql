CREATE DATABASE "green-coding";
\c green-coding;

CREATE EXTENSION "uuid-ossp";

CREATE TABLE runs (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    name text,
    uri text,
    branch text,
    commit_hash text,
    commit_timestamp timestamp with time zone,
    email text,
    categories int[],
    usage_scenario json,
    filename text,
    machine_specs jsonb,
    machine_id int DEFAULT 1,
    gmt_hash text,
    measurement_config jsonb,
    start_measurement bigint,
    end_measurement bigint,
    phases JSON DEFAULT null,
    logs text DEFAULT null,
    invalid_run text,
    last_run timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);

CREATE TABLE measurements (
    id SERIAL PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE ,
    detail_name text NOT NULL,
    metric text NOT NULL,
    value bigint NOT NULL,
    unit text NOT NULL,
    time bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);

CREATE UNIQUE INDEX measurements_get ON measurements(run_id ,metric ,detail_name ,time );
CREATE INDEX measurements_build_and_store_phase_stats ON measurements(run_id, metric, unit, detail_name);
CREATE INDEX measurements_build_phases ON measurements(metric, unit, detail_name);

CREATE TABLE network_intercepts (
    id SERIAL PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE ,
    time bigint NOT NULL,
    connection_type text NOT NULL,
    protocol text NOT NULL,
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
    available boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT NULL
);

CREATE TABLE phase_stats (
    id SERIAL PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE,
    metric text NOT NULL,
    detail_name text NOT NULL,
    phase text NOT NULL,
    value bigint NOT NULL,
    type text NOT NULL,
    max_value bigint DEFAULT NULL,
    min_value bigint DEFAULT NULL,
    unit text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);
CREATE INDEX "phase_stats_run_id" ON "phase_stats" USING HASH ("run_id");

CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    run_id uuid REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE DEFAULT null,
    type text,
    machine_id int REFERENCES machines(id) ON DELETE SET NULL ON UPDATE CASCADE DEFAULT null,
    failed boolean DEFAULT false,
    running boolean DEFAULT false,
    last_run timestamp with time zone,
    created_at timestamp with time zone DEFAULT now()
);


CREATE TABLE notes (
    id SERIAL PRIMARY KEY,
    run_id uuid REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE,
    detail_name text,
    note text,
    time bigint,
    created_at timestamp with time zone DEFAULT now()
);
CREATE INDEX "notes_run_id" ON "notes" USING HASH ("run_id");


CREATE TABLE ci_measurements (
    id SERIAL PRIMARY KEY,
    energy_value bigint,
    energy_unit text,
    repo text,
    branch text,
    workflow text,
    run_id text,
    cpu text DEFAULT NULL,
    cpu_util_avg int,
    commit_hash text DEFAULT NULL,
    label text,
    duration bigint,
    source text,
    created_at timestamp with time zone DEFAULT now()
);
CREATE INDEX "ci_measurements_get" ON ci_measurements(repo, branch, workflow, run_id, created_at);

CREATE TABLE client_status (
    id SERIAL PRIMARY KEY,
	status_code TEXT NOT NULL,
	machine_id int REFERENCES machines(id) ON DELETE SET NULL ON UPDATE CASCADE DEFAULT null,
	"data" TEXT,
	run_id uuid REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now()
);