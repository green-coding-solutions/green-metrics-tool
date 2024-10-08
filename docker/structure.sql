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
(E'DEFAULT',E'89dbf71048801678ca4abfbaa3ea8f7c651aae193357a3e23d68e21512cd07f5',E'{"api":{"quotas":{},"routes":["/v1/carbondb/add","/v1/ci/measurement/add","/v1/software/add","/v1/hog/add","/v1/authentication/data"]},"data":{"runs":{"retention":2678400},"hog_tasks":{"retention":2678400},"measurements":{"retention":2678400},"hog_coalitions":{"retention":2678400},"ci_measurements":{"retention":2678400},"hog_measurements":{"retention":2678400}},"jobs":{"schedule_modes":["one-off","daily","weekly","commit","variance"]},"machines":[1],"measurement":{"quotas":{},"settings":{"total-duration":86400,"flow-process-duration":86400}},"optimizations":["container_memory_utilization","container_cpu_utilization","message_optimization","container_build_time","container_boot_time","container_image_size"]}',E'2024-08-22 11:28:24.937262+00',NULL);



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
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
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
    energy_value bigint,
    energy_unit text,
    repo text,
    branch text,
    workflow_id text,
    workflow_name text,
    run_id text,
    cpu text,
    cpu_util_avg int,
    commit_hash text,
    label text,
    duration bigint,
    source text,
    lat text,
    lon text,
    city text,
    co2i text,
    co2eq text,
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
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
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
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
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
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


CREATE TABLE carbondb_energy_data (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    company UUID,
    machine UUID NOT NULL,
    project UUID,
    tags TEXT[],
    time_stamp BIGINT NOT NULL,
    energy_value FLOAT NOT NULL,
    co2_value FLOAT,
    carbon_intensity FLOAT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    ip_address INET,
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE TRIGGER carbondb_energy_data_moddatetime
    BEFORE UPDATE ON carbondb_energy_data
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);


CREATE INDEX idx_carbondb_company ON carbondb_energy_data(company);
CREATE INDEX idx_carbondb_machine ON carbondb_energy_data(machine);
CREATE INDEX idx_carbondb_project ON carbondb_energy_data(project);

CREATE INDEX idx_carbondb_energy_data_grouping ON carbondb_energy_data (time_stamp, machine, energy_value);


CREATE TABLE carbondb_energy_data_day (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    company UUID,
    machine UUID NOT NULL,
    project UUID,
    tags TEXT[],
    date DATE NOT NULL,
    energy_sum FLOAT NOT NULL,
    co2_sum FLOAT,
    carbon_intensity_avg FLOAT,
    record_count INT,
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE TRIGGER carbondb_energy_data_day_moddatetime
    BEFORE UPDATE ON carbondb_energy_data_day
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE INDEX idx_carbondb_hour_company ON carbondb_energy_data_day(company);
CREATE INDEX idx_carbondb_hour_machine ON carbondb_energy_data_day(machine);
CREATE INDEX idx_carbondb_hour_project ON carbondb_energy_data_day(project);
CREATE UNIQUE INDEX unique_entry ON carbondb_energy_data_day (type, company, machine, project, tags, date) NULLS NOT DISTINCT;

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
