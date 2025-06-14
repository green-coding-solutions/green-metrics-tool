CREATE TABLE changelog (
    id SERIAL PRIMARY KEY,
    message text,
    machine_id integer REFERENCES machines(id) ON DELETE SET NULL ON UPDATE CASCADE,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp without time zone
);

CREATE TRIGGER changelog_moddatetime
    BEFORE UPDATE ON changelog
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);