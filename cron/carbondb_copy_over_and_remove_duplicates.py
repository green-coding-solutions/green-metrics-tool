import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import os

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import error_helpers

# TODO: Currently this assumes all data is coming from Germany!
# We need need a mean to discern where the connection from Power HOG was coming from.
# Either we supply the power region, ip address or the coordinates

# TODO 2: This is currently only for PowerHOG. Waiting till other services fail so we can test and add it there too ...
def backfill_missing_carbon_intensity():
    query = '''
        UPDATE hog_simplified_measurements as hsm
        SET grid_intensity_cog = (SELECT ci.data->>'carbonIntensity'
            FROM carbon_intensity as ci
            WHERE ci.data->>'zone' = 'DE'
            ORDER BY ABS(EXTRACT(EPOCH FROM (hsm.created_at - ci.created_at::timestamp)))
            LIMIT 1)::int
        WHERE hsm.grid_intensity_cog IS NULL;
    '''
    DB().query(query)

    query = '''
        UPDATE hog_simplified_measurements
        SET operational_carbon_ug = ((combined_energy_uj::DOUBLE PRECISION)/1e3/3600/1000)*grid_intensity_cog
        WHERE operational_carbon_ug IS NULL;
    '''
    DB().query(query)

    query = '''
        UPDATE ci_measurements as cim
        SET carbon_intensity_g = (SELECT ci.data->>'carbonIntensity'
            FROM carbon_intensity as ci
            WHERE ci.data->>'zone' = 'DE'
            ORDER BY ABS(EXTRACT(EPOCH FROM (cim.created_at - ci.created_at::timestamp)))
            LIMIT 1)::int
        WHERE cim.carbon_intensity_g IS NULL;
    '''
    DB().query(query)

    query = '''
        UPDATE ci_measurements
        SET carbon_ug = ((energy_uj::DOUBLE PRECISION)/1e3/3600/1000)*carbon_intensity_g
        WHERE carbon_ug IS NULL;
    '''
    DB().query(query)

    # we also need to update the carbondb_data_raw table as it gets direct inserts
    query = '''
        UPDATE carbondb_data_raw as cdb
        SET carbon_intensity_g = (SELECT ci.data->>'carbonIntensity'
            FROM carbon_intensity as ci
            WHERE ci.data->>'zone' = 'DE'
            ORDER BY ABS(EXTRACT(EPOCH FROM (cdb.created_at - ci.created_at::timestamp)))
            LIMIT 1)::int
        WHERE cdb.carbon_intensity_g IS NULL;
    '''
    DB().query(query)

    query = '''
        UPDATE carbondb_data_raw
        SET carbon_kg = ((energy_kwh::DOUBLE PRECISION)*carbon_intensity_g)/1e3
        WHERE carbon_ug IS NULL;
    '''
    DB().query(query)

def copy_over_power_hog(interval=30):
    params = []
    query = '''
        INSERT INTO carbondb_data_raw
            ("type", "project", "machine", "source", "tags","time","energy_kwh","carbon_kg","carbon_intensity_g","latitude","longitude","ip_address","user_id","created_at")

            SELECT
                'machine.desktop',
                'Not-Set',
                machine_uuid,
                'Power HOG',
                '{}',
                EXTRACT(EPOCH FROM created_at) * 1e6,
                (combined_energy_uj::DOUBLE PRECISION)/1e6/3600/1000, -- to get to kWh
                (operational_carbon_ug::DOUBLE PRECISION)/1e9 + (embodied_carbon_ug/1e9), -- to get to kg
                grid_intensity_cog,  -- (carbon_intensity_g) there is no need for this column for further processing
                NULL,  -- (latitude) there is no need for this column for further processing
                NULL,  -- (longitude) there is no need for this column for further processing
                NULL,
                user_id,
                created_at
            FROM hog_simplified_measurements
    '''
    if interval:
        query = f"{query} WHERE created_at >= CURRENT_DATE - make_interval(days => %s)"
        params.append(interval)

    DB().query(query, params=params)


def copy_over_eco_ci(interval=1):
    params = []
    query = '''
        INSERT INTO carbondb_data_raw
            ("type", "project", "machine", "source", "tags","time","energy_kwh","carbon_kg","carbon_intensity_g","latitude","longitude","ip_address","user_id","created_at")

            SELECT
                filter_type,
                filter_project,
                filter_machine,
                'Eco CI',
                filter_tags,
                EXTRACT(EPOCH FROM created_at) * 1e6,
                (energy_uj::DOUBLE PRECISION)/1e6/3600/1000, -- to get to kWh
                (carbon_ug::DOUBLE PRECISION)/1e9, -- to get to kg
                -1,  -- (carbon_intensity_g) there is no need for this column for further processing
                NULL,  -- (latitude) there is no need for this column for further processing
                NULL,  -- (longitude) there is no need for this column for further processing
                ip_address,
                user_id,
                created_at
            FROM ci_measurements
    '''
    if interval:
        query = f"{query} WHERE created_at >= CURRENT_DATE - make_interval(days => %s)"
        params.append(interval)

    DB().query(query, params=params)

def copy_over_scenario_runner(interval=30):
    params = []
    query = '''
        INSERT INTO carbondb_data_raw
            ("type", "project", "machine", "source", "tags","time","energy_kwh","carbon_kg","carbon_intensity_g","latitude","longitude","ip_address","user_id","created_at")
            SELECT
                'machine.server' as type,
                'ScenarioRunner' as project,
                m.description,
                'ScenarioRunner',
                ARRAY[]::text[] as tags ,
                EXTRACT(EPOCH FROM r.created_at) * 1e6 as time,

                -- we do these two queries as subselects as if they were left joins they will blow up the table whenever we relax the condition that only one metric with same name may exist
                COALESCE((SELECT SUM(value::DOUBLE PRECISION) FROM phase_stats as p WHERE p.run_id = r.id AND p.unit = 'uJ' AND p.phase != '004_[RUNTIME]' AND p.metric LIKE '%%_energy_%%_machine')/1e6/3600/1000, 0) as energy_kwh,
                COALESCE((SELECT SUM(value::DOUBLE PRECISION) FROM phase_stats as p2 WHERE p2.run_id = r.id AND p2.unit = 'ug' AND p2.phase != '004_[RUNTIME]' AND p2.metric LIKE '%%_carbon_%%_machine')/1e9, 0) as carbon_kg,

                -1, -- there is no need for this column for further processing
                NULL,  -- there is no need for this column for further processing
                NULL,  -- there is no need for this column for further processing
                NULL,
                r.user_id,
                r.created_at
            FROM runs as r
            -- we do LEFT JOIN as we do not want to silent skip data. If a column gets NULL it will fail
            LEFT JOIN machines as m ON m.id = r.machine_id
    '''
    if interval:
        query = f"{query} WHERE r.created_at >= CURRENT_DATE - make_interval(days => %s)"
        params.append(interval)

    query = f"{query} GROUP BY r.id, m.description"

    DB().query(query, params=params)


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
        backfill_missing_carbon_intensity()
        copy_over_eco_ci()
        copy_over_scenario_runner()
        copy_over_power_hog()
        remove_duplicates()
    except Exception as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception=exc, machine=GlobalConfig().config['machine']['description'])
