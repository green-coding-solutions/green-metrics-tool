-- Host execution allows flows with "container: None" in the usage_scenario to run
-- their commands directly on the host system instead of inside a Docker container.
--
-- This is a security sensitive capability. It is granted by adding the 'host'
-- orchestrator to the user's capabilities and is off for every user by default.
-- Only the DEFAULT user (id 1), which is installed for local usage of the GMT,
-- gets the capability so that host execution works out of the box locally.
-- Cluster operators who do not want this can simply revoke it:
--   UPDATE users SET capabilities = capabilities #- '{measurement,orchestrators,host}' WHERE id = 1;

UPDATE users
SET capabilities = jsonb_set(capabilities, '{measurement,orchestrators,host}', '{}'::jsonb)
WHERE id = 1 AND capabilities->'measurement' ? 'orchestrators';
