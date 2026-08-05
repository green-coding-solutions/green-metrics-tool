CREATE TABLE softwares (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL,
    image_src text,
    category_ids integer[],
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE TRIGGER softwares_moddatetime
    BEFORE UPDATE ON softwares
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TRIGGER trg_validate_category_ids_softwares
BEFORE INSERT OR UPDATE ON softwares
FOR EACH ROW EXECUTE FUNCTION validate_category_ids();

CREATE TABLE software_tasks (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    software_id integer REFERENCES softwares(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    name text NOT NULL,
    uri text NOT NULL,
    branch text NOT NULL,
    filename text NOT NULL,
    machine_id integer NOT NULL REFERENCES machines(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    phase text NOT NULL,
    created_at timestamp with time zone NOT NULL DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE INDEX software_tasks_software_id_idx ON software_tasks(software_id);
CREATE INDEX software_tasks_name_idx ON software_tasks(name);
CREATE INDEX software_tasks_machine_id_idx ON software_tasks(machine_id);

CREATE UNIQUE INDEX software_tasks_unique_task ON software_tasks(
    software_id, name, uri, branch, filename, machine_id, phase
);


CREATE TRIGGER software_tasks_moddatetime
    BEFORE UPDATE ON software_tasks
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);


UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (capabilities->'api'->'routes') || '"\/v1\/runs\/add"'::jsonb
)
WHERE
    capabilities->'api'->'routes' ? '/v1/software/add'
    AND NOT (capabilities->'api'->'routes' ? '/v1/runs/add');

UPDATE users
SET capabilities = jsonb_set(
    capabilities,
    '{api,routes}',
    (capabilities->'api'->'routes') - '/v1/software/add'
)
WHERE capabilities->'api'->'routes' ? '/v1/software/add';