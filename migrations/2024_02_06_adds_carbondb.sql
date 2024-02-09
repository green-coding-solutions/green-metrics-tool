CREATE TABLE carbondb_energy_data (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    company UUID,
    machine UUID NOT NULL,
    project UUID,
    tags TEXT[],
    time_stamp BIGINT NOT NULL,
    energy_value FLOAT NOT NULL,
    co2_value FLOAT,
    carbon_intensity FLOAT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    ip_address INET,

    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE TRIGGER carbondb_energy_data_moddatetime
    BEFORE UPDATE ON carbondb_energy_data
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);


CREATE INDEX idx_carbondb_company ON carbondb_energy_data(company);
CREATE INDEX idx_carbondb_machine ON carbondb_energy_data(machine);
CREATE INDEX idx_carbondb_project ON carbondb_energy_data(project);


CREATE TABLE carbondb_energy_data_day (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    company UUID,
    machine UUID NOT NULL,
    project UUID,
    tags TEXT[],
    date DATE NOT NULL,
    energy_sum FLOAT NOT NULL,
    co2_sum FLOAT,
    carbon_intensity_avg FLOAT,
    record_count INT,

    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

CREATE TRIGGER carbondb_energy_data_day_moddatetime
    BEFORE UPDATE ON carbondb_energy_data_day
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);


CREATE INDEX idx_carbondb_hour_company ON carbondb_energy_data_day(company);
CREATE INDEX idx_carbondb_hour_machine ON carbondb_energy_data_day(machine);
CREATE INDEX idx_carbondb_hour_project ON carbondb_energy_data_day(project);

ALTER TABLE IF EXISTS public.carbondb_energy_data_day
    ADD CONSTRAINT unique_machine_project_date UNIQUE (machine, date);

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
