import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import error_helpers

# The main job of the compress script is to take all the data from the carbondb_data_raw table
# and compress it to daily sums.
# During this process we also transform all text fields and transform them to integers and drop them into normalized
# joined tables.

def compress_data():
    query = """

        DROP TABLE IF EXISTS carbondb_data_raw_tmp;
        CREATE TABLE carbondb_data_raw_tmp AS
        SELECT * FROM carbondb_data_raw;

        INSERT INTO carbondb_types (type, user_id)
        SELECT DISTINCT type, user_id
        FROM carbondb_data_raw
        ON CONFLICT
        DO NOTHING;

        INSERT INTO carbondb_machines (machine, user_id)
        SELECT DISTINCT machine, user_id
        FROM carbondb_data_raw
        ON CONFLICT
        DO NOTHING;


        INSERT INTO carbondb_tags (tag, user_id)
        SELECT DISTINCT unnest(tags), user_id
        FROM carbondb_data_raw
        ON CONFLICT
        DO NOTHING;

        INSERT INTO carbondb_sources (source, user_id)
        SELECT DISTINCT source, user_id
        FROM carbondb_data_raw
        ON CONFLICT
        DO NOTHING;


        INSERT INTO carbondb_projects (project, user_id)
        SELECT DISTINCT project, user_id
        FROM carbondb_data_raw
        ON CONFLICT
        DO NOTHING;


        UPDATE carbondb_data_raw_tmp SET tags = (
            SELECT ARRAY_AGG(t2.id)
            FROM UNNEST(carbondb_data_raw_tmp.tags) AS elem
            LEFT JOIN carbondb_tags AS t2 ON t2.tag = elem
        );

        UPDATE carbondb_data_raw_tmp as cdrt
        SET "type" = s.id
        FROM (SELECT "id", "type", "user_id" FROM carbondb_types) AS s
        WHERE cdrt.type = s.type AND cdrt.user_id = s.user_id;

        UPDATE carbondb_data_raw_tmp as cdrt
        SET "source" = s.id
        FROM (SELECT "id", "source", "user_id" FROM carbondb_sources) AS s
        WHERE cdrt.source = s.source AND cdrt.user_id = s.user_id;

        UPDATE carbondb_data_raw_tmp as cdrt
        SET "machine" = s.id
        FROM (SELECT "id", "machine", "user_id" FROM carbondb_machines) AS s
        WHERE cdrt.machine = s.machine AND cdrt.user_id = s.user_id;

        UPDATE carbondb_data_raw_tmp as cdrt
        SET "project" = s.id
        FROM (SELECT "id", "project", "user_id" FROM carbondb_projects) AS s
        WHERE cdrt.project = s.project AND cdrt.user_id = s.user_id;

        INSERT INTO carbondb_data (
            type,
            machine,
            project,
            source,
            tags,
            date,
            energy_kwh_sum,
            carbon_kg_sum,
            carbon_intensity_g_avg,
            record_count
        )
        SELECT
            cdr.type::int,
            cdr.machine::int,
            cdr.project::int,
            cdr.source::int,
            cdr.tags::int[],
            DATE_TRUNC('day', TO_TIMESTAMP(cdr.time / 1000000)),
            SUM(cdr.energy_kwh),
            SUM(cdr.carbon_kg),
            (SUM(cdr.energy_kwh) / SUM(cdr.carbon_kg)), -- weighted average instead of just averaging carbon_intensity
            COUNT(*)
        FROM
            carbondb_data_raw_tmp cdr
        GROUP BY
            cdr.type,
            cdr.source,
            cdr.machine,
            cdr.project,
            cdr.tags,
            DATE_TRUNC('day', TO_TIMESTAMP(cdr.time / 1000000)),
            cdr.user_id
        ON CONFLICT (type, source, machine, project, tags, date, user_id) DO UPDATE
        SET
            -- excluded will take the fields positional from the insert query. The names are not the actual column values
            -- but the calculation planned for these columns through the SELECT statement
            energy_kwh_sum = EXCLUDED.energy_kwh_sum,
            carbon_kg_sum = EXCLUDED.carbon_kg_sum,
            carbon_intensity_g_avg = EXCLUDED.carbon_intensity_g_avg,
            record_count = EXCLUDED.record_count;
    """
    DB().query(query)


if __name__ == '__main__':
    try:
        compress_data()
    except Exception as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception=exc, machine=GlobalConfig().config['machine']['description'])
