ALTER TABLE badges RENAME TO ci_measurements;
ALTER TABLE "public"."ci_measurements" ADD "label" text  NULL;
ALTER TABLE "public"."ci_measurements" ADD "source" text  NULL;