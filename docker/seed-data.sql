-- Seed data for a freshly-created schema. Split out from tables.sql so that
-- tests/test_functions.py::reset_db() can re-run just this file (after TRUNCATEing every table)
-- instead of dropping/recreating the whole schema on every single test - tables.sql's DDL only
-- needs to run once per schema.

-- Default password for authentication is DEFAULT
INSERT INTO users (
    "id",
    "name",
    "token",
    "ssh_private_key",
    "capabilities",
    "created_at",
    "updated_at"
)
VALUES (
    1,
    E'DEFAULT',
    E'89dbf71048801678ca4abfbaa3ea8f7c651aae193357a3e23d68e21512cd07f5',
    NULL,
    E'{
        "user": {
            "visible_users": [0,1],
            "is_super_user": true,
            "updateable_settings": [
                "measurement.dev_no_sleeps",
                "measurement.skip_optimizations",
                "measurement.dev_no_container_dependency_collection",
                "measurement.disabled_metric_providers",
                "measurement.flow_process_duration",
                "measurement.total_duration",
                "measurement.system_check_threshold",
                "measurement.pre_test_sleep",
                "measurement.idle_duration",
                "measurement.baseline_duration",
                "measurement.post_test_sleep",
                "measurement.phase_transition_time",
                "measurement.wait_time_dependencies",
                "measurement.skip_volume_inspect",
				"ssh_private_key",
                "docker_credentials"
            ]
        },
        "api": {
            "quotas": {},
            "routes": [
                "/v1/software",
                "/v1/software/{software_id}/tasks",
                "/v1/software/categories",
                "/v1/software/similar",
                "/v1/warnings/{run_id}",
                "/v1/insights",
                "/v1/ci/insights",
                "/v1/machines",
                "/v1/job",
                "/v2/jobs",
                "/v1/notes/{run_id}",
                "/v1/network/{run_id}",
                "/v1/repositories",
                "/v2/runs",
                "/v1/compare",
                "/v1/phase_stats/single/{run_id}",
                "/v1/measurements/single/{run_id}",
                "/v1/diff",
                "/v2/run/{run_id}",
                "/v1/optimizations/{run_id}",
                "/v1/watchlist",
                "/v1/badge/single/{run_id}",
                "/v1/badge/timeline",
                "/v1/timeline",
                "/v2/timeline",
                "/v1/ci/measurement/add",
                "/v1/ci/measurements",
                "/v1/ci/badge/get",
                "/v1/ci/runs",
                "/v1/ci/repositories",
                "/v1/ci/stats",
                "/v2/ci/measurement/add",
                "/v3/ci/measurement/add",
                "/v1/runs/add",
                "/v1/user/settings",
                "/v1/user/setting",
                "/v1/cluster/changelog",
                "/v1/cluster/status",
                "/v1/cluster/status/history",
                "/v1/carbondb/insights",
                "/v1/hog/insights",
                "/v2/carbondb/add",
                "/v2/carbondb",
                "/v2/carbondb/filters",
                "/v2/hog/add",
                "/v2/hog/top_processes",
                "/v2/hog/details",
                "/v1/run/{run_id}",
                "/v1/system-logs",
                "/v1/system-log"
            ]
        },
        "data": {
            "runs": {"retention": 2678400},
            "measurements": {"retention": 2678400},
            "ci_measurements": {"retention": 2678400}
        },
        "jobs": {
            "schedule_modes": [
                "one-off",
                "daily",
                "weekly",
                "commit",
                "variance",
                "tag",
                "commit-variance",
                "tag-variance",
                "statistical-significance"
            ]
        },
        "machines": [1],
        "measurement": {
            "quotas": {},
            "dev_no_sleeps": false,
            "skip_optimizations": false,
            "dev_no_container_dependency_collection": false,
            "allowed_volume_mounts": [],
            "dev_no_system_checks": false,
            "skip_volume_inspect": false,
            "total_duration": 86400,
            "flow_process_duration": 86400,
            "system_check_threshold": 3,
            "pre_test_sleep": 5,
            "baseline_duration": 60,
            "idle_duration": 60,
            "post_test_sleep": 5,
            "phase_transition_time": 1,
            "wait_time_dependencies": 60,
            "orchestrators": {
                "docker": {
                    "allowed_run_args": []
                }
            },
            "disabled_metric_providers": []
        },
        "optimizations": [
            "container_memory_utilization",
            "container_cpu_utilization",
            "message_optimization",
            "container_build_time",
            "container_boot_time",
            "container_image_size"
        ]
    }',
    E'2024-08-22 11:28:24.937262+00',
    NULL
);


-- Default password for user 0 is empty
INSERT INTO users ("id", "name","token","ssh_private_key","capabilities","created_at","updated_at")
VALUES (
    0,
    E'[GMT-SYSTEM]',
    E'',
    NULL,
    E'{
        "api": {
            "quotas": {},
            "routes": []
        },
        "data": {
            "ci_measurements": {
                "retention": 2678400
            },
            "measurements": {
                "retention": 2678400
            },
            "runs": {
                "retention": 2678400
            }
        },
        "jobs": {
            "schedule_modes": []
        },
        "machines": [],
        "measurement": {
        },
        "optimizations": [],
        "user": {
            "is_super_user": false
        }
    }', -- listing entries in 'measurement' has no current effect, as they are not used by the validate.py
    E'2024-11-06 11:28:24.937262+00',
    NULL
);

-- Align the identity counter
DO $$
DECLARE
    next_id bigint;
BEGIN
    SELECT COALESCE(MAX(id), 0) + 1 INTO next_id FROM users;
    EXECUTE format(
        'ALTER TABLE users ALTER COLUMN id RESTART WITH %s',
        next_id
    );
END $$;

-- Default password for authentication is DEFAULT
INSERT INTO machines ("description", "available")
VALUES
(E'Development machine for testing', true);

INSERT INTO "jobs"("type","state","name","email","url","branch","filename","usage_scenario_variables","category_ids","machine_id","message","user_id","created_at","updated_at")
	VALUES
	(E'run',E'FINISHED',E'This is a demo job - Please delete when you run in cluster mode',NULL,E'demo-url',E'demo-branch',E'demo-filename',E'{}',NULL,1,NULL,1,E'2025-10-03 07:57:29.829712+00',NULL);

INSERT INTO "categories"("id","name","parent_id")
VALUES
(1,'macOS',NULL),
(2,'Linux',NULL),
(3,'Windows',NULL),
(4,'Websites',NULL),
(5,'Command Line Programs', 2),
(6,'GUI Applications', NULL);

SELECT setval('categories_id_seq', (SELECT MAX(id) FROM categories));

INSERT INTO "cluster_status_messages"("message") VALUES('GMT is currently not running in cluster mode and thus status messages are not active - This is just a demo message to show the capabilites of the status message system. You can ignore it when using GMT locally. But please delete it when running in cluster mode');
