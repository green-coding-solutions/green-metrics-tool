-- Jobs of users with a higher capabilities.jobs.priority are picked first by the job queue.
-- Existing users get the default of 0. A priority that has already been set is not overwritten.

UPDATE users
SET capabilities = jsonb_set(capabilities, '{jobs,priority}', '0'::jsonb)
WHERE capabilities ? 'jobs' AND NOT (capabilities->'jobs') ? 'priority';
