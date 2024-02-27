CREATE TABLE artifacts (
    id SERIAL PRIMARY KEY,
    type text,
    key text,
    data json,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE TRIGGER artifacts_moddatetime
    BEFORE UPDATE ON artifacts
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE INDEX idx_artifact_select ON artifacts(type, key);