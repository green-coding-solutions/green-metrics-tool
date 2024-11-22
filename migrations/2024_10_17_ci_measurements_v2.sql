
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

ALTER TABLE "public"."ci_measurements" RENAME COLUMN "energy_value" TO "energy_uj";
ALTER TABLE "public"."ci_measurements" RENAME COLUMN "co2i" TO "carbon_intensity_g";
ALTER TABLE "public"."ci_measurements" RENAME COLUMN "co2eq" TO "carbon_ug";
ALTER TABLE "public"."ci_measurements" RENAME COLUMN "duration" TO "duration_us";

ALTER TABLE "public"."ci_measurements"
  DROP COLUMN "energy_unit",
  ADD COLUMN  "ip_address" INET,
  ADD COLUMN "filter_type" text,
  ADD COLUMN "filter_project" text,
  ADD COLUMN "filter_machine" text,
  ADD COLUMN "filter_tags" text[];

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "carbon_intensity_g" TYPE int USING "carbon_intensity_g"::int;

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "carbon_ug" TYPE DOUBLE PRECISION USING "carbon_ug"::DOUBLE PRECISION;

UPDATE ci_measurements SET energy_uj = energy_uj*1000; -- from mJ

UPDATE ci_measurements SET carbon_ug = carbon_ug*1000000; -- from g

UPDATE ci_measurements SET duration_us = duration_us*1000000; -- from s


ALTER TABLE "public"."ci_measurements" ALTER COLUMN "carbon_ug" TYPE BIGINT USING "carbon_ug"::BIGINT;

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "user_id" SET NOT NULL;
ALTER TABLE "public"."timeline_projects" ALTER COLUMN "user_id" SET NOT NULL;
ALTER TABLE "public"."hog_measurements" ALTER COLUMN "user_id" SET NOT NULL;


UPDATE ci_measurements SET filter_type = 'machine.ci' WHERE filter_type IS NULL or filter_type = '';
UPDATE ci_measurements SET filter_project = 'CI/CD' WHERE filter_project IS NULL or filter_project = '';
UPDATE ci_measurements SET filter_machine = 'unknown' WHERE filter_machine IS NULL OR filter_machine = '';
UPDATE ci_measurements SET filter_tags = '{}' WHERE filter_tags IS NULL;

ALTER TABLE "public"."ci_measurements" ALTER COLUMN "filter_type" SET NOT NULL;
ALTER TABLE "public"."ci_measurements" ALTER COLUMN "filter_project" SET NOT NULL;
ALTER TABLE "public"."ci_measurements" ALTER COLUMN "filter_machine" SET NOT NULL;
ALTER TABLE "public"."ci_measurements" ALTER COLUMN "filter_tags" SET NOT NULL;


CREATE VIEW carbondb_data_view AS
SELECT cd.*, t.type as type_str, s.source as source_str, m.machine as machine_str, p.project as project_str FROM carbondb_data as cd
LEFT JOIN carbondb_types as t ON cd.type = t.id
LEFT JOIN carbondb_sources as s ON cd.source = s.id
LEFT JOIN carbondb_machines as m ON cd.machine = m.id
LEFT JOIN carbondb_projects as p ON cd.project = p.id;

UPDATE phase_stats
SET metric = REPLACE(metric, '_co2_', '_carbon_')
WHERE metric LIKE '%_co2_%';
