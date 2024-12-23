INSERT INTO "public"."users"("id", "name","token","capabilities","created_at","updated_at")
VALUES
(0, E'[GMT-SYSTEM]',E'',E'{"user":{"is_super_user": false},"api":{"quotas":{},"routes":[]},"data":{"runs":{"retention":2678400},"hog_tasks":{"retention":2678400},"measurements":{"retention":2678400},"hog_coalitions":{"retention":2678400},"ci_measurements":{"retention":2678400},"hog_measurements":{"retention":2678400}},"jobs":{"schedule_modes":[]},"machines":[],"measurement":{"quotas":{},"settings":{"total-duration":86400,"flow-process-duration":86400}},"optimizations":[]}',E'2024-11-06 11:28:24.937262+00',NULL);

UPDATE jobs SET user_id = 0 WHERE user_id IS NULL;

UPDATE runs SET user_id = 1 WHERE user_id IS NULL and uri != 'https://github.com/green-coding-solutions/measurement-control-workload';
UPDATE runs SET user_id = 0 WHERE user_id IS NULL and uri = 'https://github.com/green-coding-solutions/measurement-control-workload';

ALTER TABLE "public"."runs" ALTER COLUMN "user_id" SET NOT NULL;
ALTER TABLE "public"."jobs" ALTER COLUMN "user_id" SET NOT NULL;