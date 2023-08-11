ALTER TABLE "ci_measurements" ADD "cpu_util_avg" int NULL;
ALTER TABLE "ci_measurements" RENAME "value" to "energy_value";
ALTER TABLE "ci_measurements" RENAME "unit" to "energy_unit";