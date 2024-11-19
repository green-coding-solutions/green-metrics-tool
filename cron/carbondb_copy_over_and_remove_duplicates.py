import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import os

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import error_helpers

def copy_over_eco_ci():
    DB().query('''
        INSERT INTO carbondb_data_raw
            ("type", "project", "machine", "source", "tags","time","energy_kwh","carbon_kg","carbon_intensity_g","latitude","longitude","ip_address","user_id","created_at")

            SELECT
                filter_type,
                filter_project,
                filter_machine,
                'Eco-CI',
                filter_tags,
                EXTRACT(EPOCH FROM created_at) * 1e6,
                (energy_uj::DOUBLE PRECISION)/1e6/3600/1000, -- to get to kWh
                (carbon_ug::DOUBLE PRECISION)/1e9, -- to get to kg
                0,  -- (carbon_intensity_g) there is no need for this column for further processing
                0.0,  -- (latitude) there is no need for this column for further processing
                0.0,  -- (longitude) there is no need for this column for further processing
                ip_address,
                user_id,
                created_at
            FROM ci_measurements
            WHERE
                created_at >= CURRENT_DATE - INTERVAL '1 DAYS';
    ''')

def copy_over_gmt():
    DB().query('''

        INSERT INTO carbondb_data_raw
            ("type", "project", "machine", "source", "tags","time","energy_kwh","carbon_kg","carbon_intensity_g","latitude","longitude","ip_address","user_id","created_at")
            SELECT
                'machine.server' as type,
                'Energy-ID' as project,
                m.description,
                'Green Metrics Tool',
                ARRAY[]::text[] as tags ,
                EXTRACT(EPOCH FROM r.created_at) * 1e6 as time,

                -- we do these two queries as subselects as if they were left joins they will blow up the table whenever we relax the condition that only one metric with same name may exist
                (SELECT SUM(value::DOUBLE PRECISION) FROM phase_stats as p WHERE p.run_id = r.id AND p.unit = 'mJ' AND p.metric LIKE '%_energy_%_machine')/1e3/3600/1000 as energy_kwh,
                (SELECT SUM(value::DOUBLE PRECISION) FROM phase_stats as p2 WHERE p2.run_id = r.id AND p2.unit = 'ug' AND p2.metric LIKE '%_carbon_%')/1e9 as carbon_kg,

                0, -- there is no need for this column for further processing
                0.0,  -- there is no need for this column for further processing
                0.0,  -- there is no need for this column for further processing
                NULL,
                r.user_id,
                r.created_at
            FROM runs as r
            -- we do LEFT JOIN as we do not want to silent skip data. If a column gets NULL it will fail
            LEFT JOIN machines as m ON m.id = r.machine_id

            WHERE
                r.user_id IS NOT NULL
                AND r.created_at >= CURRENT_DATE - INTERVAL '30 DAYS'
            GROUP BY
                r.id, m.description;

    ''')

def validate_table_constraints():
    data = DB().fetch_all('''
        SELECT
            column_name,
            is_nullable
        FROM
            information_schema.columns
        WHERE
            table_name = 'carbondb_data_raw'
            AND column_name IN ('user_id', 'time', 'energy_kwh', 'carbon_kg', 'carbon_intensity_g', 'type', 'project', 'machine', 'source', 'tags')
    ''')

    for row in data:
        if row[1] == 'YES':
            raise RuntimeError(f"{row[0]} was NULL-able: {row[1]}. CarbonDB cannot remove duplicates.")


def remove_duplicates():
    validate_table_constraints() # since the query works only if columns are not null
    DB().query('''
        DELETE FROM carbondb_data_raw a
        USING carbondb_data_raw b
        WHERE
            a.ctid < b.ctid
            AND a.time = b.time
            AND a.machine = b.machine
            AND a.type = b.type
            AND a.project = b.project
            AND a.source = b.source
            AND a.tags = b.tags
            AND a.energy_kwh = b.energy_kwh
            AND a.carbon_kg = b.carbon_kg
            AND a.user_id = b.user_id;
    ''')


if __name__ == '__main__':
    try:
        GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/../manager-config.yml")
        copy_over_eco_ci()
        copy_over_gmt()
        remove_duplicates()
    except Exception as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception=exc, machine=GlobalConfig().config['machine']['description'])
