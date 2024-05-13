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
