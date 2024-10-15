CREATE EXTENSION "hstore";

ALTER TABLE "carbondb_energy_data_day" ALTER COLUMN "tags" TYPE int[] USING tags::integer[];

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
