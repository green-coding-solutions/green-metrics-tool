import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import error_helpers

# The main job of the compress script is to take all the data from the carbondb_data_raw table
# and compress it to daily sums.
# During this process we also transform all text fields and transform them to integers and drop them into normalized
# joined tables.

########### Remove NULL values from tags
# UPDATE carbondb_data_raw
# SET tags = array_remove(tags, NULL)
# WHERE array_position(tags, NULL) IS NOT NULL;


def compress_carbondb_raw():
    query = '''

        INSERT INTO carbondb_types (type, user_id)
        SELECT DISTINCT type, user_id
        FROM carbondb_data_raw
        ON CONFLICT (type, user_id) DO NOTHING;

        INSERT INTO carbondb_machines (machine, user_id)
        SELECT DISTINCT machine, user_id
        FROM carbondb_data_raw
        ON CONFLICT (machine, user_id) DO NOTHING;

        INSERT INTO carbondb_tags (tag, user_id)
        SELECT DISTINCT unnest(tags), user_id
        FROM carbondb_data_raw
        ON CONFLICT (tag, user_id) DO NOTHING;

        INSERT INTO carbondb_sources (source, user_id)
        SELECT DISTINCT source, user_id
        FROM carbondb_data_raw
        ON CONFLICT (source, user_id) DO NOTHING;

        INSERT INTO carbondb_projects (project, user_id)
        SELECT DISTINCT project, user_id
        FROM carbondb_data_raw
        ON CONFLICT (project, user_id) DO NOTHING;

        DROP TABLE IF EXISTS carbondb_data_raw_tmp;

        CREATE TEMPORARY TABLE carbondb_data_raw_tmp AS
        SELECT * FROM carbondb_data_raw;

        UPDATE carbondb_data_raw_tmp AS cdrt
        SET "type" = s.id
        FROM carbondb_types AS s
        WHERE cdrt.type = s.type AND cdrt.user_id = s.user_id;

        UPDATE carbondb_data_raw_tmp AS cdrt
        SET "source" = s.id
        FROM carbondb_sources AS s
        WHERE cdrt.source = s.source AND cdrt.user_id = s.user_id;

        UPDATE carbondb_data_raw_tmp AS cdrt
        SET "machine" = s.id
        FROM carbondb_machines AS s
        WHERE cdrt.machine = s.machine AND cdrt.user_id = s.user_id;

        UPDATE carbondb_data_raw_tmp AS cdrt
        SET "project" = s.id
        FROM carbondb_projects AS s
        WHERE cdrt.project = s.project AND cdrt.user_id = s.user_id;

        UPDATE carbondb_data_raw_tmp
        SET tags = COALESCE(
            (SELECT ARRAY_AGG(t2.id)
            FROM UNNEST(carbondb_data_raw_tmp.tags) AS elem
            LEFT JOIN carbondb_tags AS t2 ON t2.tag = elem and t2.user_id = carbondb_data_raw_tmp.user_id)
            , ARRAY[]::int[]
        );

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
            record_count,
            user_id
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
                COALESCE(SUM(cdr.carbon_kg)*1e3 / NULLIF(SUM(cdr.energy_kwh), 0), 0), -- weighted average instead of just averaging carbon_intensity. Since the solar panel might not be producing power at all for a day, which results in 0, we need to COALESCE and insert 0 in this case
                COUNT(*),
                cdr.user_id
            FROM
                carbondb_data_raw_tmp AS cdr
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
    '''
    DB().query(query)


if __name__ == '__main__':
    try:
        GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/../manager-config.yml")
        compress_carbondb_raw()
    except Exception as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception=exc, machine=GlobalConfig().config['machine']['description'])
