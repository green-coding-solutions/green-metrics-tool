ALTER TABLE projects RENAME TO "runs";
ALTER TABLE runs RENAME COLUMN "invalid_project" TO "invalid_run";
ALTER TABLE runs ALTER COLUMN "machine_id" DROP DEFAULT;
ALTER TABLE runs ADD CONSTRAINT "machines_fk" FOREIGN KEY ("machine_id") REFERENCES machines(id) ON DELETE SET NULL ON UPDATE CASCADE;
UPDATE runs SET created_at = last_run WHERE last_run IS NOT NULL;
ALTER TABLE runs DROP COLUMN "last_run";
ALTER TABLE runs
  ADD COLUMN "job_id" int,
  ADD CONSTRAINT "job_fk" FOREIGN KEY ("job_id") REFERENCES jobs(id) ON DELETE SET NULL ON UPDATE CASCADE;


ALTER TABLE measurements RENAME COLUMN "project_id" TO "run_id";
ALTER TABLE phase_stats RENAME COLUMN "project_id" TO "run_id";
ALTER TABLE client_status RENAME COLUMN "project_id" TO "run_id";
ALTER TABLE notes RENAME COLUMN "project_id" TO "run_id";
ALTER TABLE network_intercepts RENAME COLUMN "project_id" TO "run_id";

ALTER TABLE ci_measurements DROP COLUMN "project_id";

-- create the timeline_projects table
CREATE TABLE timeline_projects (
    id SERIAL PRIMARY KEY,
    url text,
    categories integer[],
    branch text DEFAULT 'NULL'::text,
    filename text,
    machine_id integer REFERENCES machines(id) ON DELETE RESTRICT ON UPDATE CASCADE NOT NULL,
    schedule_mode text NOT NULL,
    last_scheduled timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);
-- Alter the jobs table to the new view

ALTER TABLE jobs RENAME COLUMN "project_id" TO "run_id";
ALTER TABLE jobs RENAME COLUMN "type" TO "state";
ALTER TABLE jobs ADD COLUMN "name" text;
ALTER TABLE jobs ADD COLUMN "email" text;
ALTER TABLE jobs ADD COLUMN "url" text;
ALTER TABLE jobs ADD COLUMN "filename" text;
ALTER TABLE jobs ADD COLUMN "branch" text;
ALTER TABLE jobs ADD CONSTRAINT "machines_fk" FOREIGN KEY ("machine_id") REFERENCES machines(id) ON DELETE SET NULL ON UPDATE CASCADE;
ALTER TABLE jobs ADD COLUMN "updated_at" timestamp with time zone DEFAULT now();
ALTER TABLE jobs DROP COLUMN "failed", DROP COLUMN "running", DROP COLUMN "last_run";


-- now we create updated_at columns for every table
CREATE EXTENSION "moddatetime";

ALTER TABLE measurements ADD COLUMN "updated_at" timestamp with time zone ;
ALTER TABLE phase_stats ADD COLUMN "updated_at" timestamp with time zone ;
ALTER TABLE client_status ADD COLUMN "updated_at" timestamp with time zone ;
ALTER TABLE notes ADD COLUMN "updated_at" timestamp with time zone ;
ALTER TABLE network_intercepts ADD COLUMN "updated_at" timestamp with time zone ;
ALTER TABLE ci_measurements ADD COLUMN "updated_at" timestamp with time zone ;
ALTER TABLE runs ADD COLUMN "updated_at" timestamp with time zone ;
ALTER TABLE categories ADD COLUMN "updated_at" timestamp with time zone ;
ALTER TABLE machines ADD COLUMN "updated_at" timestamp with time zone ;
ALTER TABLE ci_measurements ADD COLUMN "updated_at" timestamp with time zone ;


CREATE TRIGGER measurements_moddatetime
    BEFORE UPDATE ON measurements
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TRIGGER phase_stats_moddatetime
    BEFORE UPDATE ON phase_stats
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TRIGGER client_status_moddatetime
    BEFORE UPDATE ON client_status
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TRIGGER notes_moddatetime
    BEFORE UPDATE ON notes
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TRIGGER network_intercepts_moddatetime
    BEFORE UPDATE ON network_intercepts
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TRIGGER ci_measurements_moddatetime
    BEFORE UPDATE ON ci_measurements
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TRIGGER runs_moddatetime
    BEFORE UPDATE ON runs
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TRIGGER categories_moddatetime
    BEFORE UPDATE ON categories
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TRIGGER machines_moddatetime
    BEFORE UPDATE ON machines
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);

CREATE TRIGGER timeline_projects_moddatetime
    BEFORE UPDATE ON timeline_projects
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);
