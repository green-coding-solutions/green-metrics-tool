-- This file bootstraps the database's schema/extensions once, at first container start only
-- (docker-entrypoint-initdb.d only ever runs its scripts against a fresh/empty data volume, and
-- each *.sql file in there is its own psql invocation, defaulting to the $POSTGRES_DB database -
-- see compose.yml.example - so no CREATE DATABASE / \c is needed here or in any file after this
-- one). Table definitions live in tables.sql, seed data in seed-data.sql - both mounted right
-- after this file for that same first-boot run. tests/test_functions.py::create_test_schema()
-- re-runs tables.sql once per pytest-xdist worker, to create that worker's schema; reset_db()
-- re-runs seed-data.sql every reset, after truncating. This file itself is never re-run.
CREATE SCHEMA IF NOT EXISTS "public"; -- always present already; this is just a defensive no-op

-- Extensions are registered once per database (not per schema), so check if they are already findable somehow
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA public; -- pin to always present schema
CREATE EXTENSION IF NOT EXISTS "moddatetime" SCHEMA public; -- pin to always present schema
