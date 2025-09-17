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
INSERT INTO "public"."users"(
    "id",
    "name",
    "token",
    "capabilities",
    "created_at",
    "updated_at"
)
VALUES (
    1,
    E'DEFAULT',
    E'89dbf71048801678ca4abfbaa3ea8f7c651aae193357a3e23d68e21512cd07f5',
    E'{
        "user": {
            "visible_users": [0,1],
            "is_super_user": true,
            "updateable_settings": [
                "measurement.dev_no_sleeps",
                "measurement.dev_no_optimizations",
                "measurement.disabled_metric_providers",
                "measurement.flow_process_duration",
                "measurement.total_duration",
                "measurement.phase_padding",
                "measurement.system_check_threshold",
                "measurement.pre_test_sleep",
                "measurement.idle_duration",
                "measurement.baseline_duration",
                "measurement.post_test_sleep",
                "measurement.phase_transition_time",
                "measurement.wait_time_dependencies",
                "measurement.skip_volume_inspect"
            ]
        },
        "api": {
            "quotas": {},
            "routes": [
                "/v1/warnings/{run_id}",
                "/v1/insights",
                "/v1/ci/insights",
                "/v1/machines",
                "/v1/job",
                "/v2/jobs",
                "/v1/notes/{run_id}",
                "/v1/network/{run_id}",
                "/v1/repositories",
                "/v2/runs",
                "/v1/compare",
                "/v1/phase_stats/single/{run_id}",
                "/v1/measurements/single/{run_id}",
                "/v1/diff",
                "/v2/run/{run_id}",
                "/v1/optimizations/{run_id}",
                "/v1/watchlist",
                "/v1/badge/single/{run_id}",
                "/v1/badge/timeline",
                "/v1/timeline",
                "/v1/ci/measurement/add",
                "/v1/ci/measurements",
                "/v1/ci/badge/get",
                "/v1/ci/runs",
                "/v1/ci/repositories",
                "/v1/ci/stats",
                "/v2/ci/measurement/add",
                "/v1/software/add",
                "/v1/user/settings",
                "/v1/user/setting"
            ]
        },
        "data": {
            "runs": {"retention": 2678400},
            "measurements": {"retention": 2678400},
            "ci_measurements": {"retention": 2678400}
        },
        "jobs": {
            "schedule_modes": [
                "one-off",
                "daily",
                "weekly",
                "commit",
                "variance",
                "tag",
                "commit-variance",
                "tag-variance",
                "statistical-significance"
            ]
        },
        "machines": [1],
        "measurement": {
            "phase_padding": true,
            "quotas": {},
            "dev_no_sleeps": false,
            "dev_no_optimizations": false,
            "allow_unsafe": false,
            "skip_unsafe": true,
            "skip_system_checks": false,
            "skip_volume_inspect": false,
            "total_duration": 86400,
            "flow_process_duration": 86400,
            "system_check_threshold": 3,
            "pre_test_sleep": 5,
            "baseline_duration": 60,
            "idle_duration": 60,
            "post_test_sleep": 5,
            "phase_transition_time": 1,
            "wait_time_dependencies": 60,
            "orchestrators": {
                "docker": {
                    "allowed_run_args": []
                }
            },
            "disabled_metric_providers": []
        },
        "optimizations": [
            "container_memory_utilization",
            "container_cpu_utilization",
            "message_optimization",
            "container_build_time",
            "container_boot_time",
            "container_image_size"
        ]
    }',
    E'2024-08-22 11:28:24.937262+00',
    NULL
);


-- Default password for user 0 is empty
INSERT INTO "public"."users"("id", "name","token","capabilities","created_at","updated_at")
VALUES (
    0,
    E'[GMT-SYSTEM]',
    E'',
    E'{
        "api": {
            "quotas": {},
            "routes": []
        },
        "data": {
            "ci_measurements": {
                "retention": 2678400
            },
            "measurements": {
                "retention": 2678400
            },
            "runs": {
                "retention": 2678400
            }
        },
        "jobs": {
            "schedule_modes": []
        },
        "machines": [],
        "measurement": {
        },
        "optimizations": [],
        "user": {
            "is_super_user": false
        }
    }', -- listing entries in 'measurement' has no current effect, as they are not used by the validate.py
    E'2024-11-06 11:28:24.937262+00',
    NULL
);

SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));


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
    usage_scenario_variables jsonb NOT NULL DEFAULT '{}',
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
    usage_scenario_variables jsonb NOT NULL DEFAULT '{}',
    usage_scenario_dependencies jsonb,
    filename text NOT NULL,
    machine_specs jsonb,
    runner_arguments json,
    machine_id int NOT NULL REFERENCES machines(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    gmt_hash text,
    measurement_config jsonb,
    start_measurement bigint,
    end_measurement bigint,
    phases JSON,
    logs jsonb,
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
    unit text NOT NULL,
    sampling_rate_configured int NOT NULL
);

CREATE UNIQUE INDEX measurement_metrics_get ON measurement_metrics(run_id,metric,detail_name); -- technically we could allow also different units, but we want to see the use case for that first. Also a lot of code relies on detail_name to be the final discriminator (e.g. metric providers .transform(utils.df_fill_mean) etc.m which then need to be rewritten)
CREATE INDEX measurement_metrics_build_and_store_phase_stats ON measurement_metrics(run_id,metric,detail_name,unit);
CREATE INDEX measurement_metrics_build_phases ON measurement_metrics(metric,detail_name,unit);

CREATE TABLE measurement_values (
    id SERIAL PRIMARY KEY, -- although not strictly needed PostgreSQL seems to perform way better with it and can vacuum more efficiently
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
    sampling_rate_avg int,
    sampling_rate_max int,
    sampling_rate_95p int,
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

CREATE TABLE warnings (
    id SERIAL PRIMARY KEY,
    run_id uuid REFERENCES runs(id) ON DELETE CASCADE ON UPDATE CASCADE,
    message text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE INDEX "warnings_run_id" ON "warnings" USING HASH ("run_id");
CREATE TRIGGER warnings_moddatetime
    BEFORE UPDATE ON warnings
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
    note text CHECK (length(note) <= 1024),
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

CREATE TABLE watchlist (
    id SERIAL PRIMARY KEY,
    name text,
    image_url text,
    repo_url text,
    categories integer[],
    branch text NOT NULL,
    filename text NOT NULL,
    usage_scenario_variables jsonb NOT NULL DEFAULT '{}',
    machine_id integer REFERENCES machines(id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    schedule_mode text NOT NULL,
    last_scheduled timestamp with time zone,
    last_marker text,
    user_id integer NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER watchlist_moddatetime
    BEFORE UPDATE ON watchlist
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

CREATE TABLE changelog (
    id SERIAL PRIMARY KEY,
    message text,
    machine_id integer REFERENCES machines(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE TRIGGER changelog_moddatetime
    BEFORE UPDATE ON changelog
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);
