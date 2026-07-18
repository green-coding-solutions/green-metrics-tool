-- This file bootstraps the database's schemas/extensions once, at first container start only
-- (docker-entrypoint-initdb.d only ever runs its scripts against a fresh/empty data volume, and
-- each *.sql file in there is its own psql invocation, defaulting to the $POSTGRES_DB database -
-- see compose.yml.example - so no CREATE DATABASE / \c is needed here or in any file after this
-- one). Table definitions live in tables.sql instead: it is mounted right after this file for
-- that same first-boot run, but is also re-run standalone (never this file) by
-- tests/test_functions.py::reset_db() to reset test data without recreating the schemas.

-- Schemas and extensions, created once here at first container boot and never again (this file
-- is never re-run - see the comment above). tests/test_functions.py::reset_db() only re-runs
-- tables.sql, against whatever schema is first in its own search_path, so table/trigger
-- definitions there must stay idempotent - but the schemas and extensions themselves only ever
-- need to exist once, database-wide, which is why they live here instead.
CREATE SCHEMA IF NOT EXISTS "public"; -- This is always present for everyone
CREATE SCHEMA IF NOT EXISTS "production"; -- This is where the production database lives

-- Extensions are registered once per database (not per schema), so check if they are already findable somehow
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA public; -- pin to always present schema
CREATE EXTENSION IF NOT EXISTS "moddatetime" SCHEMA public; -- pin to always present schema

