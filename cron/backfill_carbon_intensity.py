#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os
import json
import fcntl

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

import requests
from cachetools import cached

from lib.db import DB
from lib.global_config import GlobalConfig
from lib import error_helpers
from lib.utils import runtime_dir
from lib.cache_definitions import NoNoneOrNegativeValuesCache

################################################
################# ECO CI #######################
################################################

def process(table):

    print(f"Current rows in DB where {table}.carbon_intensity_g is missing in last 30 Minutes", fetch_carbon_intensity_missing(table, count_only=True))

    updated_rows = update_carbon_intensity_from_db_cache(table)

    print('Updated rows', updated_rows)

    print(f"Rows after db cached update where {table}.carbon_intensity_g is missing in last 30 Minutes", fetch_carbon_intensity_missing(table, count_only=True))

    data = fetch_carbon_intensity_missing(table)
    backfill_carbon_intensity_missing(table, data)

    print(f"Rows left after manual row-level update where {table}.carbon_intensity_g is missing in last 30 Minutes", fetch_carbon_intensity_missing(table, count_only=True))

def update_carbon_intensity_from_db_cache(table):
    # Backfilled carbon intensity data should only be 30 minutes apart
    query = f"""
        WITH carbon_missing AS (
            SELECT DISTINCT ON (from_table.id)
                from_table.id,
                (ci.data->>'carbonIntensity')::int AS carbon_intensity_g
            FROM {table} from_table
            JOIN carbon_intensity ci
              ON ci.latitude = from_table.latitude
             AND ci.longitude = from_table.longitude
             AND ABS(EXTRACT(EPOCH FROM (from_table.created_at - ci.created_at::timestamp))) < EXTRACT(EPOCH FROM INTERVAL '30 MINUTES')
            WHERE from_table.carbon_intensity_g IS NULL
            ORDER BY
                from_table.id,
                ABS(EXTRACT(EPOCH FROM (from_table.created_at - ci.created_at::timestamp))) ASC
            LIMIT 1
        )
        UPDATE {table} from_table
        SET carbon_intensity_g = cm.carbon_intensity_g
        FROM carbon_missing cm
        WHERE
            from_table.id = cm.id
            AND cm.carbon_intensity_g IS NOT NULL
        RETURNING from_table.id, from_table.carbon_intensity_g;
    """
    return DB().fetch_all(query)

def fetch_carbon_intensity_missing(table, count_only=False):
    if count_only:
        selection = 'COUNT(*)'
    else:
        selection = 'id, latitude, longitude'

    query = f"""
        SELECT {selection}
        FROM {table}
        WHERE
            carbon_intensity_g is NULL
            AND latitude IS NOT NULL
            AND longitude IS NOT NULL
            AND created_at > NOW() - INTERVAL '30 MINUTES'
    """

    data = DB().fetch_all(query)
    return data if data else []

def backfill_carbon_intensity_missing(table, data):
    query = f"UPDATE {table} SET carbon_intensity_g = %s WHERE id = %s"

    for row in data:
        row_id = row[0]
        row_latitude = row[1]
        row_longitude = row[2]
        carbon_intensity_g = get_carbon_intensity(row_latitude, row_longitude)
        print('Filling', carbon_intensity_g, 'for id', row_id)
        DB().query(query, params=(carbon_intensity_g, row_id))

def update_eco_ci_carbon():
    query = '''
        UPDATE ci_measurements
        SET carbon_ug = ((energy_uj::DOUBLE PRECISION)/1e3/3600/1000)*carbon_intensity_g
        WHERE
            carbon_ug IS NULL
            AND carbon_intensity_g IS NOT NULL -- needed so we do not make useless NULL updates
        RETURNING id, carbon_ug;
    '''
    return DB().fetch_all(query)

def update_power_hog_carbon():
    query = '''
        UPDATE hog_simplified_measurements
        SET operational_carbon_ug = ((combined_energy_uj::DOUBLE PRECISION)/1e3/3600/1000)*carbon_intensity_g
        WHERE
            operational_carbon_ug IS NULL
            AND carbon_intensity_g IS NOT NULL -- needed so we do not make useless NULL updates
        RETURNING id, operational_carbon_ug;
    '''
    return DB().fetch_all(query)

def update_carbondb_data_raw_carbon():
    query = '''
        UPDATE carbondb_data_raw
        SET carbon_kg = (energy_kwh*carbon_intensity_g)/1e3
        WHERE
            carbon_kg IS NULL
            AND carbon_intensity_g IS NOT NULL -- needed so we do not make useless NULL updates
        RETURNING id, carbon_kg;
    '''
    return DB().fetch_all(query)


# The decorator will not work between workers, but since uvicorn_worker.UvicornWorker is using asyncIO it has some functionality between requests
@cached(cache=NoNoneOrNegativeValuesCache(maxsize=1024, ttl=3600)) # 60 Minutes
def get_carbon_intensity(latitude, longitude):

    if latitude is None or longitude is None:
        error_helpers.log_error('Calling get_carbon_intensity without lat/long')
        return None

    if not (electricitymaps_token := GlobalConfig().config.get('electricity_maps_token')):
        raise ValueError('You need to specify an electricitymap token in the config!')

    if electricitymaps_token == 'testing':
        # If we are running tests we always return 1000
        return 1000

    headers = {'auth-token': electricitymaps_token }
    params = {'lat': latitude, 'lon': longitude }

    response = requests.get('https://api.electricitymap.org/v3/carbon-intensity/latest', params=params, headers=headers, timeout=10)
    print(f"Accessing electricitymap with {latitude} {longitude}")
    if response.status_code == 200:
        resp_data = response.json()
        query = "INSERT INTO carbon_intensity (latitude, longitude, data) VALUES (%s, %s, %s)"
        DB().query(query=query, params=(latitude, longitude, json.dumps(resp_data)))

        return resp_data.get('carbonIntensity')

    raise RuntimeError(f"Could not get carbon intensity from Electricitymaps.org for {params}", response=response)

if __name__ == '__main__':
    try:
        GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/../manager-config.yml")

        lock_path = os.path.join(runtime_dir(), "gmt_backfill_carbon_intensity.lock")
        with open(lock_path, "w", encoding='UTF-8') as lock_file:

            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB) # can raise BlockingIOError

            process('ci_measurements')
            process('hog_simplified_measurements')
            process('carbondb_data_raw')

            result = update_eco_ci_carbon()
            print('Updated carbon values for eco ci', result)

            result = update_power_hog_carbon()
            print('Updated carbon values for power hog', result)

            result = update_carbondb_data_raw_carbon()
            print('Updated carbon values for carbondb data raw', result)

            fcntl.flock(lock_file, fcntl.LOCK_UN) # release lock here only after successful processing. not in finally

    except Exception as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception=exc, machine=GlobalConfig().config['machine']['description'])
