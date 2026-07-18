CREATE SCHEMA IF NOT EXISTS "gmt_test";

-- Create ten worker schemas ahead of time
-- Upgrade this is stronger parallelization is wanted
CREATE SCHEMA IF NOT EXISTS "gmt_test_gw0";
CREATE SCHEMA IF NOT EXISTS "gmt_test_gw1";
CREATE SCHEMA IF NOT EXISTS "gmt_test_gw2";
CREATE SCHEMA IF NOT EXISTS "gmt_test_gw3";
CREATE SCHEMA IF NOT EXISTS "gmt_test_gw4";
CREATE SCHEMA IF NOT EXISTS "gmt_test_gw5";
CREATE SCHEMA IF NOT EXISTS "gmt_test_gw6";
CREATE SCHEMA IF NOT EXISTS "gmt_test_gw7";
CREATE SCHEMA IF NOT EXISTS "gmt_test_gw8";
CREATE SCHEMA IF NOT EXISTS "gmt_test_gw9";
