CREATE DATABASE "green-coding";
\c green-coding;

CREATE SCHEMA IF NOT EXISTS "public";

CREATE EXTENSION "uuid-ossp";
CREATE EXTENSION "moddatetime";

CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name text,
    token text NOT NULL,
    capabilities JSONB NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE UNIQUE INDEX name_unique ON users(name text_ops);
CREATE UNIQUE INDEX token_unique ON users(token text_ops);

CREATE TRIGGER users_moddatetime
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

-- Default password for authentication is DEFAULT
INSERT INTO "public"."users"("name","token","capabilities","created_at","updated_at")
VALUES
(E'DEFAULT',E'89dbf71048801678ca4abfbaa3ea8f7c651aae193357a3e23d68e21512cd07f5',E'{"api":{"quotas":{},"routes":["/v2/carbondb/filters","/v2/carbondb","/v2/carbondb/add","/v2/ci/measurement/add","/v1/ci/measurement/add","/v1/software/add","/v1/hog/add","/v1/authentication/data"]},"data":{"runs":{"retention":2678400},"hog_tasks":{"retention":2678400},"measurements":{"retention":2678400},"hog_coalitions":{"retention":2678400},"ci_measurements":{"retention":2678400},"hog_measurements":{"retention":2678400}},"jobs":{"schedule_modes":["one-off","daily","weekly","commit","variance","tag","commit-variance","tag-variance"]},"machines":[1],"measurement":{"quotas":{},"settings":{"total-duration":86400,"flow-process-duration":86400}},"optimizations":["container_memory_utilization","container_cpu_utilization","message_optimization","container_build_time","container_boot_time","container_image_size"]}',E'2024-08-22 11:28:24.937262+00',NULL);

CREATE TABLE machines (
    id SERIAL PRIMARY KEY,
    description text,
    available boolean DEFAULT false,
    status_code text,
    jobs_processing text,
    cooldown_time_after_job integer,
    base_temperature integer,
    current_temperature integer,
    gmt_hash text,
    gmt_timestamp timestamp with time zone,
    configuration json,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER machines_moddatetime
    BEFORE UPDATE ON machines
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

-- Default password for authentication is DEFAULT
INSERT INTO "public"."machines"("description", "available")
VALUES
(E'Local machine', true);


CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    type text,
    state text,
    name text,
    email text,
    url text,
    branch text,
    filename text,
    categories int[],
    machine_id int REFERENCES machines(id) ON DELETE SET NULL ON UPDATE CASCADE,
    message text,
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER jobs_moddatetime
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TABLE runs (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    job_id integer REFERENCES jobs(id) ON DELETE SET NULL ON UPDATE CASCADE UNIQUE,
    name text,
    uri text,
    branch text NOT NULL,
    commit_hash text,
    commit_timestamp timestamp with time zone,
    email text,
    categories int[],
    usage_scenario json,
    filename text NOT NULL,
    machine_specs jsonb,
    runner_arguments json,
    machine_id int REFERENCES machines(id) ON DELETE SET NULL ON UPDATE CASCADE,
    gmt_hash text,
    measurement_config jsonb,
    start_measurement bigint,
    end_measurement bigint,
    phases JSON,
    logs text,
    invalid_run text,
    failed boolean DEFAULT false,
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE, -- this must allowed to be null for CLI runs
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER runs_moddatetime
    BEFORE UPDATE ON runs
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);


CREATE TABLE measurements (
    id SERIAL PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE ,
    detail_name text NOT NULL,
    metric text NOT NULL,
    value bigint NOT NULL,
    unit text NOT NULL,
    time bigint NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE UNIQUE INDEX measurements_get ON measurements(run_id ,metric ,detail_name ,time );
CREATE INDEX measurements_build_and_store_phase_stats ON measurements(run_id, metric, unit, detail_name);
CREATE INDEX measurements_build_phases ON measurements(metric, unit, detail_name);
CREATE TRIGGER measurements_moddatetime
    BEFORE UPDATE ON measurements
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);


CREATE TABLE network_intercepts (
    id SERIAL PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE ,
    time bigint NOT NULL,
    connection_type text NOT NULL,
    protocol text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER network_intercepts_moddatetime
    BEFORE UPDATE ON network_intercepts
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);


CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name text,
    parent_id int REFERENCES categories(id) ON DELETE CASCADE ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER categories_moddatetime
    BEFORE UPDATE ON categories
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);


CREATE TABLE phase_stats (
    id SERIAL PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE,
    metric text NOT NULL,
    detail_name text NOT NULL,
    phase text NOT NULL,
    value bigint NOT NULL,
    type text NOT NULL,
    max_value bigint,
    min_value bigint,
    unit text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE INDEX "phase_stats_run_id" ON "phase_stats" USING HASH ("run_id");
CREATE TRIGGER phase_stats_moddatetime
    BEFORE UPDATE ON phase_stats
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);




CREATE TABLE notes (
    id SERIAL PRIMARY KEY,
    run_id uuid REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE,
    detail_name text,
    note text,
    time bigint,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE INDEX "notes_run_id" ON "notes" USING HASH ("run_id");
CREATE TRIGGER notes_moddatetime
    BEFORE UPDATE ON notes
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);


CREATE TABLE ci_measurements (
    id SERIAL PRIMARY KEY,
    energy_uj bigint,
    repo text,
    branch text,
    workflow_id text,
    workflow_name text,
    run_id text,
    cpu text,
    cpu_util_avg int,
    commit_hash text,
    label text,
    duration_us bigint,
    source text,
    lat text,
    lon text,
    city text,
    carbon_intensity_g int,
    carbon_ug bigint,
    ip_address INET,
    filter_type text NOT NULL,
    filter_project text NOT NULL,
    filter_machine text NOT NULL,
    filter_tags text[] NOT NULL,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE INDEX "ci_measurements_subselect" ON ci_measurements(repo, branch, workflow_id, created_at);
CREATE TRIGGER ci_measurements_moddatetime
    BEFORE UPDATE ON ci_measurements
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);


CREATE TABLE client_status (
    id SERIAL PRIMARY KEY,
	status_code TEXT NOT NULL,
	machine_id int REFERENCES machines(id) ON DELETE SET NULL ON UPDATE CASCADE,
	"data" TEXT,
	run_id uuid REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER client_status_moddatetime
    BEFORE UPDATE ON client_status
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TABLE timeline_projects (
    id SERIAL PRIMARY KEY,
    name text,
    url text,
    categories integer[],
    branch text NOT NULL,
    filename text NOT NULL,
    machine_id integer REFERENCES machines(id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    schedule_mode text NOT NULL,
    last_scheduled timestamp with time zone,
    last_marker text,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER timeline_projects_moddatetime
    BEFORE UPDATE ON timeline_projects
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TABLE hog_measurements (
    id SERIAL PRIMARY KEY,
    time bigint NOT NULL,
    machine_uuid uuid NOT NULL,
    elapsed_ns bigint NOT NULL,
    combined_energy int,
    cpu_energy int,
    gpu_energy int,
    ane_energy int,
    energy_impact int,
    thermal_pressure text,
    settings jsonb,
    data jsonb,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER hog_measurements_moddatetime
    BEFORE UPDATE ON hog_measurements
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE INDEX idx_hog_measurements_machine_uuid ON hog_measurements USING hash (machine_uuid);
CREATE INDEX idx_hog_measurements_time ON hog_measurements (time);


CREATE TABLE hog_coalitions (
    id SERIAL PRIMARY KEY,
    measurement integer REFERENCES hog_measurements(id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    name text NOT NULL,
    cputime_ns bigint,
    cputime_per int,
    energy_impact int,
    diskio_bytesread bigint,
    diskio_byteswritten bigint,
    intr_wakeups bigint,
    idle_wakeups bigint,
    data jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER hog_coalitions_moddatetime
    BEFORE UPDATE ON hog_coalitions
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE INDEX idx_coalition_energy_impact ON hog_coalitions(energy_impact);
CREATE INDEX idx_coalition_name ON hog_coalitions(name);
CREATE INDEX idx_coalition_measurement ON hog_coalitions(measurement);

CREATE TABLE hog_tasks (
    id SERIAL PRIMARY KEY,
    coalition integer REFERENCES hog_coalitions(id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    name text NOT NULL,
    cputime_ns bigint,
    cputime_per int,
    energy_impact int,
    bytes_received bigint,
    bytes_sent bigint,
    diskio_bytesread bigint,
    diskio_byteswritten bigint,
    intr_wakeups bigint,
    idle_wakeups bigint,
    data jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER hog_tasks_moddatetime
    BEFORE UPDATE ON hog_tasks
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE INDEX idx_task_coalition ON hog_tasks(coalition);

CREATE TABLE optimizations (
    id SERIAL PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE ,
    title text NOT NULL,
    label text,
    criticality text,
    reporter text,
    icon text,
    description text NOT NULL,
    link text,

    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE TRIGGER optimizations_moddatetime
    BEFORE UPDATE ON optimizations
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE INDEX optimizations_runs ON optimizations(run_id);


CREATE TABLE carbondb_types (
    id SERIAL PRIMARY KEY,
    type text NOT NULL,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE UNIQUE INDEX carbondb_types_unique ON carbondb_types(type text_ops,user_id int4_ops);


CREATE TABLE carbondb_tags (
    id SERIAL PRIMARY KEY,
    tag text NOT NULL,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE UNIQUE INDEX carbondb_tags_unique ON carbondb_tags(tag text_ops,user_id int4_ops);


CREATE TABLE carbondb_machines (
    id SERIAL PRIMARY KEY,
    machine text NOT NULL,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE UNIQUE INDEX carbondb_machines_unique ON carbondb_machines(machine text_ops,user_id int4_ops);

CREATE TABLE carbondb_projects (
    id SERIAL PRIMARY KEY,
    project text NOT NULL,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE UNIQUE INDEX carbondb_projects_unique ON carbondb_projects(project text_ops,user_id int4_ops);

CREATE TABLE carbondb_sources (
    id SERIAL PRIMARY KEY,
    source text NOT NULL,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE UNIQUE INDEX carbondb_sources_unique ON carbondb_sources(source text_ops,user_id int4_ops);


CREATE TABLE carbondb_data_raw (
    id SERIAL PRIMARY KEY,
    type text NOT NULL,
    project text NOT NULL,
    machine text NOT NULL,
    source text NOT NULL CHECK (source IN ('CUSTOM', 'Eco-CI', 'Green Metrics Tool', 'Power HOG')),
    tags text[] NOT NULL,
    time BIGINT NOT NULL,
    energy_kwh DOUBLE PRECISION NOT NULL,
    carbon_kg DOUBLE PRECISION NOT NULL,
    carbon_intensity_g int NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    ip_address INET,
    user_id int NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE TRIGGER carbondb_data_raw_moddatetime
    BEFORE UPDATE ON carbondb_data_raw
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

-- note that the carbondb_data uses integer fields instead of type fields. This is because we
-- operate for querying and filtering only on integers for performance

CREATE TABLE carbondb_data (
    id SERIAL PRIMARY KEY,
    type integer NOT NULL REFERENCES carbondb_types(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    project integer NOT NULL REFERENCES carbondb_projects(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    machine integer NOT NULL REFERENCES carbondb_machines(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    source integer NOT NULL REFERENCES carbondb_sources(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    tags int[] NOT NULL,
    date DATE NOT NULL,
    energy_kwh_sum DOUBLE PRECISION NOT NULL,
    carbon_kg_sum DOUBLE PRECISION NOT NULL,
    carbon_intensity_g_avg int NOT NULL,
    record_count INT,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE UNIQUE INDEX carbondb_data_unique_entry ON carbondb_data(type int4_ops,project int4_ops,machine int4_ops,source int4_ops,tags array_ops,date date_ops,user_id int4_ops) NULLS NOT DISTINCT;

CREATE TABLE ip_data (
    ip_address INET,
    data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ip_address, created_at)
);

CREATE TABLE carbon_intensity (
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (latitude, longitude, created_at)
);


CREATE VIEW carbondb_data_view AS
SELECT cd.*, t.type as type_str, s.source as source_str, m.machine as machine_str, p.project as project_str FROM carbondb_data as cd
LEFT JOIN carbondb_types as t ON cd.type = t.id
LEFT JOIN carbondb_sources as s ON cd.source = s.id
LEFT JOIN carbondb_machines as m ON cd.machine = m.id
LEFT JOIN carbondb_projects as p ON cd.project = p.id;