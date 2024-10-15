CREATE TABLE carbondb_data_raw (
    id SERIAL PRIMARY KEY,
    type text NOT NULL,
    project text NOT NULL,
    machine text NOT NULL,
    source text NOT NULL,
    tags text[],
    time BIGINT NOT NULL,
    energy int NOT NULL,
    carbon int,
    carbon_intensity int,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    ip_address INET,
    user_id int REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
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
    tags int[],
    date DATE NOT NULL,
    energy_sum int NOT NULL,
    carbon_sum int,
    carbon_intensity_avg int,
    record_count INT,
    user_id integer REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);


CREATE TRIGGER carbondb_data_moddatetime
    BEFORE UPDATE ON carbondb_data
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE UNIQUE INDEX unique_entry ON carbondb_data (type, project, machine, source, tags, date, user_id) NULLS NOT DISTINCT;


CREATE TABLE carbondb_types (
    id SERIAL PRIMARY KEY,
    type text NOT NULL,
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE UNIQUE INDEX carbondb_types_unique ON carbondb_types(type text_ops,user_id int4_ops);


CREATE TABLE carbondb_tags (
    id SERIAL PRIMARY KEY,
    tag text NOT NULL,
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE UNIQUE INDEX carbondb_tags_unique ON carbondb_tags(tag text_ops,user_id int4_ops);


CREATE TABLE carbondb_machines (
    id SERIAL PRIMARY KEY,
    machine text NOT NULL,
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE UNIQUE INDEX carbondb_machines_unique ON carbondb_machines(machine text_ops,user_id int4_ops);

CREATE TABLE carbondb_projects (
    id SERIAL PRIMARY KEY,
    project text NOT NULL,
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE UNIQUE INDEX carbondb_projects_unique ON carbondb_projects(project text_ops,user_id int4_ops);

CREATE TABLE carbondb_sources (
    id SERIAL PRIMARY KEY,
    source text NOT NULL,
    user_id integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE UNIQUE INDEX carbondb_sources_unique ON carbondb_sources(source text_ops,user_id int4_ops);



INSERT INTO carbondb_types (type, user_id)
SELECT DISTINCT type, user_id
FROM carbondb_energy_data_day WHERE user_id IS NOT NULL AND type IS NOT NULL;

INSERT INTO carbondb_machines (machine, user_id)
SELECT DISTINCT machine, user_id
FROM carbondb_energy_data_day WHERE user_id IS NOT NULL AND machine IS NOT NULL;

INSERT INTO carbondb_tags (tag, user_id)
SELECT DISTINCT unnest(tags), user_id
FROM carbondb_energy_data_day WHERE user_id IS NOT NULL AND tags IS NOT NULL;

INSERT INTO carbondb_projects (project, user_id)
SELECT DISTINCT project, user_id
FROM carbondb_energy_data_day WHERE user_id IS NOT NULL AND project IS NOT NULL;


UPDATE carbondb_energy_data_day as cedd
SET "tags"[1] = (SELECT "id" FROM carbondb_tags WHERE "tags"[1] = "tag" and carbondb_tags.user_id = cedd.user_id)
WHERE "tags"[1] IS NOT NULL;

UPDATE carbondb_energy_data_day as cedd
SET "tags"[2] = (SELECT "id" FROM carbondb_tags WHERE "tags"[2] = "tag" and carbondb_tags.user_id = cedd.user_id)
WHERE "tags"[2] IS NOT NULL;

UPDATE carbondb_energy_data_day as cedd
SET "tags"[3] = (SELECT "id" FROM carbondb_tags WHERE "tags"[3] = "tag" and carbondb_tags.user_id = cedd.user_id)
WHERE "tags"[3] IS NOT NULL;


UPDATE carbondb_energy_data_day as cedd
SET "tags"[4] = (SELECT "id" FROM carbondb_tags WHERE "tags"[4] = "tag" and carbondb_tags.user_id = cedd.user_id)
WHERE "tags"[4] IS NOT NULL;


UPDATE carbondb_energy_data_day as cedd
SET "tags"[5] = (SELECT "id" FROM carbondb_tags WHERE "tags"[5] = "tag" and carbondb_tags.user_id = cedd.user_id)
WHERE "tags"[5] IS NOT NULL;


INSERT INTO carbondb_data (type, project, machine, source, tags, date, energy_sum, carbon_sum, carbon_intensity_avg, record_count, user_id)
SELECT
    (SELECT id FROM carbondb_types as ct WHERE ct.type = cedd.type::text AND ct.user_id = cedd.user_id),
    (SELECT id FROM carbondb_projects as ct WHERE ct.project = cedd.project::text AND ct.user_id = cedd.user_id),
    (SELECT id FROM carbondb_machines as ct WHERE ct.machine = cedd.machine::text AND ct.user_id = cedd.user_id),
    1, -- source is not available, so we just set to
    tags::int[],
    date, energy_sum, co2_sum, carbon_intensity_avg, record_count, user_id
FROM carbondb_energy_data_day as cedd;
