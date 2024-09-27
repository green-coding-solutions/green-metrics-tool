ALTER TABLE carbondb_energy_data_day drop constraint unique_machine_project_date;
TRUNCATE carbondb_energy_data_day;
CREATE UNIQUE INDEX unique_entry ON carbondb_energy_data_day (type, company, machine, project, tags, date) NULLS NOT DISTINCT;
