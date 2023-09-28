CREATE TABLE hog_measurements (
    id SERIAL PRIMARY KEY,
    time bigint NOT NULL,
    machine_uuid uuid NOT NULL,
    elapsed_ns bigint NOT NULL,
    combined_energy int,
    cpu_energy int,
    gpu_energy int,
    ane_energy int,
    energy_impact int,
    thermal_pressure text,
    settings jsonb,
    data jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER hog_measurements_moddatetime
    BEFORE UPDATE ON hog_measurements
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE INDEX idx_hog_measurements_machine_uuid ON hog_measurements USING hash (machine_uuid);
CREATE INDEX idx_hog_measurements_time ON hog_measurements (time);


CREATE TABLE hog_coalitions (
    id SERIAL PRIMARY KEY,
    measurement integer REFERENCES hog_measurements(id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    name text NOT NULL,
    cputime_ns bigint,
    cputime_per int,
    energy_impact int,
    diskio_bytesread bigint,
    diskio_byteswritten bigint,
    intr_wakeups bigint,
    idle_wakeups bigint,
    data jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER hog_coalitions_moddatetime
    BEFORE UPDATE ON hog_coalitions
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE INDEX idx_coalition_energy_impact ON hog_coalitions(energy_impact);
CREATE INDEX idx_coalition_name ON hog_coalitions(name);

CREATE TABLE hog_tasks (
    id SERIAL PRIMARY KEY,
    coalition integer REFERENCES hog_coalitions(id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    name text NOT NULL,
    cputime_ns bigint,
    cputime_per int,
    energy_impact int,
    bytes_received bigint,
    bytes_sent bigint,
    diskio_bytesread bigint,
    diskio_byteswritten bigint,
    intr_wakeups bigint,
    idle_wakeups bigint,

    data jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
CREATE TRIGGER hog_tasks_moddatetime
    BEFORE UPDATE ON hog_tasks
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE INDEX idx_task_coalition ON hog_tasks(coalition);