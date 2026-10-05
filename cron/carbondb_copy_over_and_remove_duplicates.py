import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import os

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import error_helpers

# We copy over a larger timespan than the merge window in case server errors happend or the job did not run for a couple of days
COPY_OVER_LOOKBACK_DAYS = round(GlobalConfig().config['cluster']['carbondb_merge_window_days'] * 1.5)

# Must be larger than the copy over lookback to not leave duplicates behind. In case this is reduced choose at least merge window + 1 days to avoid race conditions
CLEANUP_LOOKBACK_DAYS = GlobalConfig().config['cluster']['carbondb_merge_window_days'] * 2

def check_config():
    merge_window = GlobalConfig().config['cluster']['carbondb_merge_window_days']
    if not isinstance(merge_window, int) or isinstance(merge_window, bool) or merge_window < 1:
        raise ValueError(f"carbondb_merge_window_days must be a positive integer, but is {merge_window}. Please check your settings for carbondb_merge_window_days in the config.yml")

    # Data may arrive up to the merge window late, so copy over must reach further back or late data is never copied
    if COPY_OVER_LOOKBACK_DAYS <= merge_window:
        raise ValueError(f"Copy over timeframe ({COPY_OVER_LOOKBACK_DAYS} days) must be strictly larger than merge window ({merge_window} days). Please check your settings for carbondb_merge_window_days in the config.yml")

    if COPY_OVER_LOOKBACK_DAYS >= CLEANUP_LOOKBACK_DAYS:
        raise ValueError(f"Copy over timeframe ({COPY_OVER_LOOKBACK_DAYS} days) must be strictly smaller than cleanup timeframe ({CLEANUP_LOOKBACK_DAYS} days). Please check your settings for carbondb_merge_window_days in the config.yml")

def copy_over_power_hog(full_history=False):
    query = '''
        INSERT INTO carbondb_data_raw
            ("type", "project", "machine", "source", "tags","time","energy_kwh","carbon_kg","carbon_intensity_g","latitude","longitude","ip_address","user_id","created_at")

            SELECT
                'machine.desktop',
                'Not-Set',
                machine_uuid,
                'Power HOG',
                '{}',
                "timestamp" * 1e3, -- timestamp is already milliseconds. thus only 1e3
                (combined_energy_uj::DOUBLE PRECISION)/1e6/3600/1000, -- to get to kWh
                (operational_carbon_ug::DOUBLE PRECISION)/1e9 + (embodied_carbon_ug/1e9), -- to get to kg
                carbon_intensity_g,
                latitude,
                longitude,
                ip_address,
                user_id,
                NOW()
            FROM hog_simplified_measurements
            -- filter on the measurement timestamp and not on created_at, as Power HOG data may arrive up to the merge window late.
            -- This aligns the copy over with remove_duplicates and compress, which both filter on carbondb_data_raw.time
            WHERE %s OR "timestamp" > EXTRACT(EPOCH FROM ((NOW() - make_interval(days => %s))::date::timestamp))*1e3 -- timestamp is in milliseconds
    '''

    DB().query(query, params=(full_history, COPY_OVER_LOOKBACK_DAYS))


def copy_over_eco_ci(full_history=False):
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
                carbon_intensity_g,
                latitude,
                longitude,
                ip_address,
                user_id,
                NOW()
            FROM ci_measurements
            WHERE %s OR created_at > CURRENT_DATE - make_interval(days => %s)
    '''

    DB().query(query, params=(full_history, COPY_OVER_LOOKBACK_DAYS))

def copy_over_scenario_runner(full_history=False):
    query = '''
        INSERT INTO carbondb_data_raw
            ("type", "project", "machine", "source", "tags","time","energy_kwh","carbon_kg","carbon_intensity_g","latitude","longitude","ip_address","user_id","run_id","created_at")
            SELECT
                'machine.server' as type,
                'ScenarioRunner' as project,
                m.description,
                'ScenarioRunner',
                ARRAY[]::text[] as tags ,
                EXTRACT(EPOCH FROM r.created_at) * 1e6 as time,

                -- we do these two queries as subselects as if they were left joins they will blow up the table whenever we relax the condition that only one metric with same name may exist
                COALESCE((SELECT SUM(value::DOUBLE PRECISION) FROM phase_stats as p WHERE p.run_id = r.id AND p.unit = 'uJ' AND p.phase != '004_[RUNTIME]' AND p.metric LIKE '%%_energy_%%_machine')/1e6/3600/1000, 0) as energy_kwh,
                COALESCE((SELECT SUM(value::DOUBLE PRECISION) FROM phase_stats as p2 WHERE p2.run_id = r.id AND p2.unit = 'ugCO2e' AND p2.phase != '004_[RUNTIME]' AND p2.metric LIKE '%%_carbon_%%_machine')/1e9, 0) as carbon_kg,

                NULL, -- there simply is no carbon intensity atm
                NULL, -- there simply is no latitude as no IP is present
                NULL, -- there simply is no longitude as no IP is present
                NULL, -- no connecting IP was used to transmit the data
                r.user_id,
                r.id,
                NOW()
            FROM runs as r
            -- we do LEFT JOIN as we do not want to silent skip data. If a column gets NULL it will fail
            LEFT JOIN machines as m ON m.id = r.machine_id
            WHERE %s OR r.created_at > CURRENT_DATE - make_interval(days => %s)
            GROUP BY r.id, m.description
            -- runs are keyed so that changed values (e.g. run finished after previous copy over or phase_stats got recalculated) replace the old row instead of creating a second one
            ON CONFLICT (run_id) DO UPDATE SET
                machine = EXCLUDED.machine,
                time = EXCLUDED.time,
                energy_kwh = EXCLUDED.energy_kwh,
                carbon_kg = EXCLUDED.carbon_kg,
                user_id = EXCLUDED.user_id
            WHERE (carbondb_data_raw.machine, carbondb_data_raw.time, carbondb_data_raw.energy_kwh, carbondb_data_raw.carbon_kg, carbondb_data_raw.user_id)
                IS DISTINCT FROM (EXCLUDED.machine, EXCLUDED.time, EXCLUDED.energy_kwh, EXCLUDED.carbon_kg, EXCLUDED.user_id) -- avoid needless writes and updated_at bumps
    '''

    DB().query(query, params=(full_history, COPY_OVER_LOOKBACK_DAYS))


def validate_table_constraints():
    data = DB().fetch_all('''
        SELECT id
        FROM
            carbondb_data_raw
        WHERE
            (user_id IS NULL -- null by design. only guard for broken schema
            OR time IS NULL -- null by design. only guard for broken schema
            OR energy_kwh IS NULL -- null by design. only guard for broken schema
            OR carbon_kg IS NULL  -- can be null bc of backfill
            OR type IS NULL -- null by design. only guard for broken schema
            OR project IS NULL -- null by design. only guard for broken schema
            OR machine IS NULL -- null by design. only guard for broken schema
            OR source IS NULL -- null by design. only guard for broken schema
            OR tags IS NULL) -- null by design. only guard for broken schema
            AND created_at > NOW() - make_interval(days => %s)
            AND created_at < NOW() - INTERVAL '30 MINUTES' -- data just arrived can be null, before it is backfilled
     ''', params=(CLEANUP_LOOKBACK_DAYS, ))

    if data:
        raise RuntimeError(f"NULL values found `carbondb_data_raw` - {data}")

def remove_duplicates(full_history=False):
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
            AND a.carbon_kg = b.carbon_kg -- if this column is null the rows will simply not match. so not problematic. we check later with validate_table_constraints
            AND a.user_id = b.user_id
            AND a.run_id IS NOT DISTINCT FROM b.run_id -- rows of different ScenarioRunner runs are never duplicates. Same run cannot occur twice due to unique index
            AND (%s OR a.time > EXTRACT(EPOCH FROM ((NOW() - make_interval(days => %s))::date::timestamp))*1e6) -- Time filter must be starting from midnight and not include elapsed minutes in the day to work with copy over which cuts off time info
    ''', params=(full_history, CLEANUP_LOOKBACK_DAYS))


if __name__ == '__main__':
    try:
        GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/../manager-config.yml")
        print('check_config')
        check_config()
        print('copy_over_eco_ci')
        copy_over_eco_ci()
        print('copy_over_scenario_runner')
        copy_over_scenario_runner()
        print('copy_over_power_hog')
        copy_over_power_hog()
        print('remove_duplicates')
        remove_duplicates()
        print('validate_table_constraints against ')
        validate_table_constraints()

    except Exception as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception=exc, machine=GlobalConfig().config['machine']['description'])
