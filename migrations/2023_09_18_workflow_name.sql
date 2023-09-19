ALTER TABLE "ci_measurements" ADD "workflow_name" text NULL;
ALTER TABLE "ci_measurements" RENAME "workflow" to "workflow_id";