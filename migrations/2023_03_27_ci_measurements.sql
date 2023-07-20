ALTER TABLE badges RENAME TO ci_measurements;
ALTER TABLE "ci_measurements" ADD "label" text  NULL;
ALTER TABLE "ci_measurements" ADD "source" text  NULL;