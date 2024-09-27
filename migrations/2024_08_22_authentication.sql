CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name text,
    token text NOT NULL,
    capabilities JSONB NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

ALTER TABLE "jobs" ADD COLUMN "user_id" integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "timeline_projects" ADD COLUMN "user_id" integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "runs" ADD COLUMN "user_id" integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "ci_measurements" ADD COLUMN "user_id" integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "hog_measurements" ADD COLUMN "user_id" integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "carbondb_energy_data" ADD COLUMN "user_id" integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE "carbondb_energy_data_day" ADD COLUMN "user_id" integer REFERENCES users(id) ON DELETE SET NULL ON UPDATE CASCADE;


CREATE UNIQUE INDEX name_unique ON users(name text_ops);
CREATE UNIQUE INDEX token_unique ON users(token text_ops);

INSERT INTO "users"("id","name","token","capabilities","created_at","updated_at")
VALUES
(1,E'DEFAULT',E'89dbf71048801678ca4abfbaa3ea8f7c651aae193357a3e23d68e21512cd07f5',E'{"api":{"quotas":{},"routes":["/v1/carbondb/add","/v1/ci/measurement/add","/v1/software/add","/v1/hog/add","/v1/authentication/data"]},"data":{"runs":{"retention":2678400},"hog_tasks":{"retention":2678400},"measurements":{"retention":2678400},"hog_coalitions":{"retention":2678400},"ci_measurements":{"retention":2678400},"hog_measurements":{"retention":2678400}},"jobs":{"schedule_modes":["one-off","daily","weekly","commit","variance"]},"machines":[1],"measurement":{"quotas":{},"settings":{"total-duration":86400,"flow-process-duration":86400}},"optimizations":["container_memory_utilization","container_cpu_utilization","message_optimization","container_build_time","container_boot_time","container_image_size"]}',E'2024-08-22 11:28:24.937262+00',NULL);

CREATE TRIGGER users_moddatetime
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

-- Default password for authentication is DEFAULT
INSERT INTO "public"."machines"("description", "available")
VALUES
(E'Local machine', true);