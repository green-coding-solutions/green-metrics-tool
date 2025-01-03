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

CREATE UNIQUE INDEX name_unique ON users(name);
CREATE UNIQUE INDEX token_unique ON users(token);

CREATE TRIGGER users_moddatetime
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

-- Default password for authentication is DEFAULT
INSERT INTO "public"."users"("name","token","capabilities","created_at","updated_at")
VALUES
(E'DEFAULT',E'89dbf71048801678ca4abfbaa3ea8f7c651aae193357a3e23d68e21512cd07f5',E'{"user":{"visible_users":[0,1],"is_super_user": true},"api":{"quotas":{},"routes":["/v1/machines","/v1/jobs","/v1/notes/{run_id}","/v1/network/{run_id}","/v1/repositories","/v1/runs","/v1/compare","/v1/phase_stats/single/{run_id}","/v1/measurements/single/{run_id}","/v1/diff","/v1/run/{run_id}","/v1/optimizations/{run_id}","/v1/timeline-projects","/v1/badge/single/{run_id}","/v1/badge/timeline","/v1/timeline","/v1/ci/measurement/add","/v1/ci/measurements","/v1/ci/badge/get","/v1/ci/runs","/v1/ci/repositories","/v1/ci/stats","/v2/ci/measurement/add","/v1/software/add","/v1/authentication/data"]},"data":{"runs":{"retention":2678400},"measurements":{"retention":2678400},"ci_measurements":{"retention":2678400}},"jobs":{"schedule_modes":["one-off","daily","weekly","commit","variance","tag","commit-variance","tag-variance"]},"machines":[1],"measurement":{"quotas":{},"settings":{"total-duration":86400,"flow-process-duration":86400}},"optimizations":["container_memory_utilization","container_cpu_utilization","message_optimization","container_build_time","container_boot_time","container_image_size"]}',E'2024-08-22 11:28:24.937262+00',NULL);

-- Default password for user 0 is empty
INSERT INTO "public"."users"("id", "name","token","capabilities","created_at","updated_at")
VALUES
(0, E'[GMT-SYSTEM]',E'',E'{"user":{"is_super_user": false},"api":{"quotas":{},"routes":[]},"data":{"runs":{"retention":2678400},"hog_tasks":{"retention":2678400},"measurements":{"retention":2678400},"hog_coalitions":{"retention":2678400},"ci_measurements":{"retention":2678400},"hog_measurements":{"retention":2678400}},"jobs":{"schedule_modes":[]},"machines":[],"measurement":{"quotas":{},"settings":{"total-duration":86400,"flow-process-duration":86400}},"optimizations":[]}',E'2024-11-06 11:28:24.937262+00',NULL);

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
    machine_id int REFERENCES machines(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    message text,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
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
    categories int[],
    usage_scenario json,
    filename text NOT NULL,
    machine_specs jsonb,
    runner_arguments json,
    machine_id int REFERENCES machines(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    gmt_hash text,
    measurement_config jsonb,
    start_measurement bigint,
    end_measurement bigint,
    phases JSON,
    logs text,
    invalid_run text,
    failed boolean DEFAULT false,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER runs_moddatetime
    BEFORE UPDATE ON runs
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);


CREATE TABLE measurement_metrics (
    id SERIAL PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE,
    metric text NOT NULL,
    detail_name text NOT NULL,
    unit text NOT NULL
);

CREATE UNIQUE INDEX measurement_metrics_get ON measurement_metrics(run_id,metric,detail_name); -- technically we could allow also different units, but we want to see the use case for that first
CREATE INDEX measurement_metrics_build_and_store_phase_stats ON measurement_metrics(run_id,metric,detail_name,unit);
CREATE INDEX measurement_metrics_build_phases ON measurement_metrics(metric,detail_name,unit);

CREATE TABLE measurement_values (
    measurement_metric_id int NOT NULL REFERENCES measurement_metrics(id) ON DELETE CASCADE ON UPDATE CASCADE,
    value bigint NOT NULL,
    time bigint NOT NULL
);

CREATE INDEX measurement_values_mmid ON measurement_values(measurement_metric_id);
CREATE UNIQUE INDEX measurement_values_unique ON measurement_values(measurement_metric_id, time);


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
    sampling_rate_avg int NOT NULL,
    sampling_rate_max int NOT NULL,
    sampling_rate_95p int NOT NULL,
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
    user_id integer NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
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
    machine_id int REFERENCES machines(id) ON DELETE RESTRICT ON UPDATE CASCADE,
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
    user_id integer NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER timeline_projects_moddatetime
    BEFORE UPDATE ON timeline_projects
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

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
