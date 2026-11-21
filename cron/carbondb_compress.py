import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import os

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import error_helpers

from cron.carbondb_copy_over_and_remove_duplicates import evaluate_config

# The main job of the compress script is to take all the data from the carbondb_data_raw table
# and compress it to daily sums.
# During this process we also transform all text fields and transform them to integers and drop them into normalized
# joined tables.

########### Remove NULL values from tags
# UPDATE carbondb_data_raw
# SET tags = array_remove(tags, NULL)
# WHERE array_position(tags, NULL) IS NOT NULL;


# None for copy_over_lookback_limit compresses the full history
def compress_carbondb_raw(copy_over_lookback_limit):
    # Only days within the copy over lookback can still receive or change rows in carbondb_data_raw. Older days are final
    # and do not need to be re-aggregated.
    # Time filter must be starting from midnight and not include elapsed minutes in the day to work with select later which cuts off time info
    if copy_over_lookback_limit is None:
        time_filter = 'TRUE'
    else:
        # The right side must be cast to bigint. EXTRACT returns numeric, which would cast the column instead and prevent index usage
        time_filter = f"time > (EXTRACT(EPOCH FROM ((NOW() - make_interval(days => {int(copy_over_lookback_limit)}))::date::timestamp))*1e6)::bigint"

    # The lookup tables only need entries for values that end up in carbondb_data. Older rows were already compressed
    # in earlier runs and thus already have their lookup entries. So we only build them from the temp table instead of
    # scanning the full carbondb_data_raw.
    # DISTINCT on (value, user_id) first is a cheap hash aggregate. ARRAY_AGG(DISTINCT ...) would sort every group instead.
    # The WHERE on the conflict branch skips rewriting rows that already contain all user_ids, which avoids
    # creating dead tuples for every lookup row on every run.
    lookup_queries = []
    for table, column, source_select in (
        ('carbondb_types', 'type', 'SELECT DISTINCT type AS value, user_id FROM carbondb_data_raw_tmp'),
        ('carbondb_machines', 'machine', 'SELECT DISTINCT machine AS value, user_id FROM carbondb_data_raw_tmp'),
        ('carbondb_sources', 'source', 'SELECT DISTINCT source AS value, user_id FROM carbondb_data_raw_tmp'),
        ('carbondb_projects', 'project', 'SELECT DISTINCT project AS value, user_id FROM carbondb_data_raw_tmp'),
        # tags can only be unnested in a subquery and not directly in GROUP BY
        ('carbondb_tags', 'tag', 'SELECT DISTINCT unnest(tags) AS value, user_id FROM carbondb_data_raw_tmp'),
    ):
        lookup_queries.append(f'''
            INSERT INTO {table} ({column}, user_ids)
            SELECT value, ARRAY_AGG(user_id ORDER BY user_id)
            FROM ({source_select}) AS sub
            GROUP BY value
            ON CONFLICT ({column}) DO UPDATE
            SET user_ids = ARRAY(
                SELECT DISTINCT u FROM unnest({table}.user_ids || excluded.user_ids) AS u ORDER BY u
            )
            WHERE NOT {table}.user_ids @> excluded.user_ids;
        ''')
    lookup_queries = '\n'.join(lookup_queries)

    # Query contains multiple statements, which psycopg cannot run with server-side bound params. Thus values are inlined
    query = f'''
        -- Serialize concurrent compress runs (cron and tools/rebuild_carbondb.py). Must come before the snapshot below, as otherwise
        -- an earlier run with an older snapshot could commit after a later run and overwrite newer aggregates with stale values.
        -- Lock is released automatically on COMMIT / ROLLBACK as the whole query runs in one transaction
        SELECT pg_advisory_xact_lock(hashtext('carbondb_compress'));

        DROP TABLE IF EXISTS carbondb_data_raw_tmp;

        -- Only the columns needed for compression. Rows are never updated in place, as every UPDATE would write
        -- a new version of every row and multiply the size of the temp table
        CREATE TEMPORARY TABLE carbondb_data_raw_tmp AS
        SELECT
            type,
            source,
            machine,
            project,
            tags,
            DATE_TRUNC('day', TO_TIMESTAMP(time / 1000000))::date AS date,
            energy_kwh,
            operational_carbon_kg,
            embodied_carbon_kg,
            user_id
        FROM carbondb_data_raw
        WHERE
            {time_filter}
            AND operational_carbon_kg IS NOT NULL; -- guarded in carbondb_copy_over that we do not miss rows continuously;

        -- temp tables are not touched by autovacuum. Without statistics the planner assumes wrong sizes for the joins and aggregates below
        ANALYZE carbondb_data_raw_tmp;

        {lookup_queries}

        -- tags arrays repeat heavily, so we resolve every distinct array only once instead of once per row
        CREATE TEMPORARY TABLE carbondb_tags_map_tmp AS
        SELECT
            dt.tags,
            COALESCE(
                (SELECT ARRAY_AGG(s.id ORDER BY elem.ord)
                FROM UNNEST(dt.tags) WITH ORDINALITY AS elem(tag, ord)
                LEFT JOIN carbondb_tags AS s ON s.tag = elem.tag)
                , ARRAY[]::int[]
            ) AS tag_ids
        FROM (SELECT DISTINCT tags FROM carbondb_data_raw_tmp) AS dt;

        ANALYZE carbondb_tags_map_tmp;

        -- the text columns are unique in the lookup tables and the lookups were just filled with all (value, user_id)
        -- combinations from carbondb_data_raw_tmp. Thus a plain join on the text column is sufficient
        INSERT INTO carbondb_data (
            type,
            machine,
            project,
            source,
            tags,
            date,
            energy_kwh_sum,
            operational_carbon_kg_sum,
            embodied_carbon_kg_sum,
            carbon_intensity_g_avg,
            record_count,
            user_id
        )
            SELECT
                t.id,
                m.id,
                p.id,
                s.id,
                tm.tag_ids,
                cdr.date,
                SUM(cdr.energy_kwh),
                SUM(cdr.operational_carbon_kg),
                SUM(cdr.embodied_carbon_kg),
                -- only operational carbon stems from the grid, so embodied carbon must not be part of the intensity
                COALESCE(SUM(cdr.operational_carbon_kg)*1e3 / NULLIF(SUM(cdr.energy_kwh), 0), 0), -- weighted average instead of just averaging carbon_intensity. Since the solar panel might not be producing power at all for a day, which results in 0, we need to COALESCE and insert 0 in this case
                COUNT(*),
                cdr.user_id
            FROM
                carbondb_data_raw_tmp AS cdr
            JOIN carbondb_types AS t ON t.type = cdr.type
            JOIN carbondb_machines AS m ON m.machine = cdr.machine
            JOIN carbondb_projects AS p ON p.project = cdr.project
            JOIN carbondb_sources AS s ON s.source = cdr.source
            JOIN carbondb_tags_map_tmp AS tm ON tm.tags = cdr.tags
            GROUP BY
                t.id,
                s.id,
                m.id,
                p.id,
                tm.tag_ids,
                cdr.date,
                cdr.user_id
        ON CONFLICT (type, source, machine, project, tags, date, user_id) DO UPDATE
        SET
            -- excluded will take the fields positional from the insert query. The names are not the actual column values
            -- but the calculation planned for these columns through the SELECT statement
            energy_kwh_sum = EXCLUDED.energy_kwh_sum,
            operational_carbon_kg_sum = EXCLUDED.operational_carbon_kg_sum,
            embodied_carbon_kg_sum = EXCLUDED.embodied_carbon_kg_sum,
            carbon_intensity_g_avg = EXCLUDED.carbon_intensity_g_avg,
            record_count = EXCLUDED.record_count;

        DROP TABLE carbondb_tags_map_tmp;
        DROP TABLE carbondb_data_raw_tmp;
    '''
    DB().query(query)

if __name__ == '__main__':
    try:
        GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/../manager-config.yml")

        COPY_OVER_LOOKBACK_LIMIT, _ = evaluate_config()
        compress_carbondb_raw(COPY_OVER_LOOKBACK_LIMIT)
    except Exception as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception=exc, machine=GlobalConfig().config['machine']['description'])
    finally:
        DB.shutdown_if_initialized()
