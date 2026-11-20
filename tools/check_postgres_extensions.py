#!/usr/bin/env python3
# Logs a WARNING to the PostgreSQL server log for every installed extension that is older than
# the version shipped with the running server (e.g. after a pg_upgrade). Fix with: ALTER EXTENSION <name> UPDATE;
# Called from docker/startup_gunicorn.sh on every container start.
from lib.db import DB

DB().query("""
    DO $$
    DECLARE ext record;
    BEGIN
        FOR ext IN
            SELECT e.extname, e.extversion, a.default_version
            FROM pg_extension e JOIN pg_available_extensions a ON a.name = e.extname
            WHERE e.extversion <> a.default_version
        LOOP
            RAISE WARNING 'Extension % is outdated (installed: %, available: %). Run: ALTER EXTENSION "%" UPDATE;',
                ext.extname, ext.extversion, ext.default_version, ext.extname;
        END LOOP;
    END $$;
""")
