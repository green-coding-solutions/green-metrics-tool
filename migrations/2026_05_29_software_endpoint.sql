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

CREATE TRIGGER software_tasks_moddatetime
    BEFORE UPDATE ON software_tasks
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);
