-- This file bootstraps the physical database once, at first container start only
-- (docker-entrypoint-initdb.d only ever runs its scripts against a fresh/empty data volume).
-- CREATE DATABASE has no IF NOT EXISTS in Postgres, so it must never be re-run after that first
-- boot. Schema/extensions/tables live in tables.sql instead: it is mounted right after this file
-- for that same first-boot run, but is also re-run standalone (never this file) by
-- tests/test_functions.py::reset_db() to reset test data without recreating the database itself.
CREATE DATABASE "green-coding";
\c green-coding;
