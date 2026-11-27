-- Cluster status messages can now be scoped to a machine and / or a service.
-- NULL in machine_id / service means the message affects all machines / services.

CREATE TYPE cluster_service AS ENUM ('CarbonDB', 'Eco CI', 'ScenarioRunner', 'Power HOG');

ALTER TABLE cluster_status_messages
    ADD COLUMN machine_id integer REFERENCES machines(id) ON DELETE RESTRICT ON UPDATE CASCADE, -- we use RESTRICT to clean up old messages. Otherwise they would become global
    ADD COLUMN service cluster_service DEFAULT 'ScenarioRunner';
