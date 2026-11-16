#!/usr/bin/env python3

# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os
import re
import glob
import json
import fcntl
from datetime import datetime, timedelta, timezone
from functools import cache

import requests

from lib.db import DB
from lib.global_config import GlobalConfig
from lib import error_helpers
from lib.utils import runtime_dir

# The column that holds the time of the measurement. It differs from created_at when data arrives late or is copied over.
TIME_COLUMNS = {
    'ci_measurements': 'from_table.created_at',
    'hog_simplified_measurements': 'TO_TIMESTAMP(from_table."timestamp" / 1e3)', # milliseconds
    'carbondb_data_raw': 'TO_TIMESTAMP(from_table.time / 1e6)', # microseconds
}

# Limits the rows to what CarbonDB and Power HOG still accept. This is on the time of the measurement and not on created_at, as late
# data would otherwise be repaired after carbondb_compress.py stopped looking at it. Uses the plain columns so that indexes can be used.
LOOKBACK_FILTERS = {
    'ci_measurements': 'from_table.created_at > NOW() - make_interval(days => %s)',
    'hog_simplified_measurements': 'from_table."timestamp" > EXTRACT(EPOCH FROM NOW() - make_interval(days => %s)) * 1e3', # milliseconds
    'carbondb_data_raw': 'from_table.time > EXTRACT(EPOCH FROM NOW() - make_interval(days => %s)) * 1e6', # microseconds
}

# Same data that the carbon simulation in the frontend uses (frontend/js/simulation-yearly.js)
YEARLY_CO2_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'frontend', 'js', 'yearly_co2')

################################################
################# ECO CI #######################
################################################

def process(table):

    data = fetch_carbon_intensity_missing(table)
    print(f"Rows in DB where {table}.carbon_intensity_g is missing in merge window:", len(data))

    if not data:
        return

    backfilled_ids = backfill_carbon_intensity_missing(table, data)

    print(f"Rows backfilled where {table}.carbon_intensity_g was missing in merge window:", len(backfilled_ids))

    # Do not go back to the DB to re-check. We already know from the backfill above exactly which of the
    # initially-missing ids got updated. Leftovers are expected, as data points can still be outstanding or there is no
    # data for the country. They must not raise, as this would stop all other rows and tables from being processed.
    leftover_ids = [row[0] for row in data if row[0] not in backfilled_ids]
    if leftover_ids:
        print(f"Rows in {table} left without carbon_intensity_g as no data is available yet: {len(leftover_ids)}. First IDs:", leftover_ids[:20])

def fetch_carbon_intensity_missing(table):
    # The country is only taken from an ip_data entry within 30 days of the row, as this is how long we assume an IP to keep its
    # owner. See cron/backfill_geo.py. We compare to created_at as the row got its IP when it was received. A row without such
    # an entry stays without carbon intensity. The lookback of the rows however is the merge window. These two are independent.
    query = f"""
        SELECT from_table.id, ip.country_code, {TIME_COLUMNS[table]}, from_table.created_at
        FROM {table} from_table
        LEFT JOIN LATERAL (
            SELECT ip_data.country_code
            FROM ip_data
            WHERE
                ip_data.ip_address = from_table.ip_address
                AND ABS(EXTRACT(EPOCH FROM (from_table.created_at - ip_data.created_at))) < EXTRACT(EPOCH FROM INTERVAL '30 DAYS')
            ORDER BY ABS(EXTRACT(EPOCH FROM (from_table.created_at - ip_data.created_at))) ASC
            LIMIT 1
        ) ip ON TRUE
        WHERE
            from_table.carbon_intensity_g is NULL
            AND from_table.latitude IS NOT NULL
            AND from_table.longitude IS NOT NULL
            AND {LOOKBACK_FILTERS[table]}
    """

    data = DB().fetch_all(query, params=(GlobalConfig().config['cluster']['carbondb_merge_window_days'],))
    return data if data else []

def backfill_carbon_intensity_missing(table, data):
    query = f"UPDATE {table} SET carbon_intensity_g = %s WHERE id = %s"

    updated_ids = []
    for row_id, country_code, measured_at, created_at in data:
        carbon_intensity_g = get_carbon_intensity(country_code, measured_at, created_at)
        if carbon_intensity_g is None:
            continue
        print('Filling', carbon_intensity_g, 'for id', row_id)
        DB().query(query, params=(carbon_intensity_g, row_id))
        updated_ids.append(row_id)

    return updated_ids

def update_eco_ci_carbon():
    query = '''
        UPDATE ci_measurements
        SET carbon_ug = ((energy_uj::DOUBLE PRECISION)/3600/1000)*carbon_intensity_g
        WHERE
            carbon_ug IS NULL
            AND carbon_intensity_g IS NOT NULL -- needed so we do not make useless NULL updates
        RETURNING id, carbon_ug;
    '''
    return DB().fetch_all(query)

def update_power_hog_carbon():
    query = '''
        UPDATE hog_simplified_measurements
        SET operational_carbon_ug = ((combined_energy_uj::DOUBLE PRECISION)/3600/1000)*carbon_intensity_g
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


@cache
def get_yearly_carbon_intensities():
    latest_file = max(glob.glob(os.path.join(YEARLY_CO2_DIR, 'yearly_*.js')))

    with open(latest_file, 'r', encoding='utf-8') as file:
        match = re.search(r'export const data = (\{.*\})', file.read())

    if not match:
        raise RuntimeError(f"Could not find yearly carbon intensity data in {latest_file}")

    return json.loads(match.group(1))

def get_yearly_carbon_intensity(country_code):
    entry = get_yearly_carbon_intensities().get(country_code)
    return round(entry['carbonIntensity']['value']) if entry else None

def get_elephant_url():
    if not (elephant_url := GlobalConfig().config.get('elephant_url')):
        raise ValueError('You need to specify an elephant_url in the config!')

    return elephant_url

# Providers report final values with a lag of some hours. Rows wait this long for a data point at or after their time from
# the most preferred provider of their region. After that they use the closest data point in the fence from the most
# preferred provider that has any, or if there is none the yearly average.
def get_elephant_max_wait():
    hours = GlobalConfig().config['elephant_max_wait_hours']

    # Must be smaller than the lookback in fetch_carbon_intensity_missing() or rows are never given a value
    max_hours = GlobalConfig().config['cluster']['carbondb_merge_window_days'] * 24
    if not isinstance(hours, int) or isinstance(hours, bool) or not 0 < hours < max_hours:
        raise ValueError(f"elephant_max_wait_hours must be an integer between 1 and {max_hours - 1} (carbondb_merge_window_days in hours), but is {hours}. Please check your settings in the config.yml")

    return timedelta(hours=hours)

# The history is only requested this far around the time of a row. So a data point further away can never be selected.
def get_elephant_fence():
    minutes = GlobalConfig().config['elephant_fence_minutes']

    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 1:
        raise ValueError(f"elephant_fence_minutes must be a positive integer, but is {minutes}. Please check your settings in the config.yml")

    return timedelta(minutes=minutes)

# Rows are grouped into buckets of this size to share one fenced request.
def get_elephant_fence_bucket_minutes():
    minutes = GlobalConfig().config['elephant_fence_bucket_minutes']

    if not isinstance(minutes, int) or isinstance(minutes, bool) or not 0 < minutes <= 60:
        raise ValueError(f"elephant_fence_bucket_minutes must be an integer between 1 and 60, but is {minutes}. Please check your settings in the config.yml")

    return minutes

# Sort key that orders the providers of a region by the config. Elephant names them <provider>_<region>
def get_provider_preference(region, provider):
    preferred_names = GlobalConfig().config['elephant_preferred_providers']
    preferred_providers = [f"{name.lower()}_{region.lower()}" for name in preferred_names]

    rank = preferred_providers.index(provider) if provider in preferred_providers else len(preferred_providers)
    return (rank, provider)

# Returns the providers per region. Regions that Elephant lists without a provider have no data and are not included.
@cache
def get_elephant_providers():
    response = requests.get(f"{get_elephant_url()}/providers", timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Could not get providers from Elephant. Status: {response.status_code}. Response: {response.text}")

    providers_by_region = {}
    for _, region, provider in response.json():
        providers_by_region.setdefault(region.upper(), []).append(provider)

    return providers_by_region

# Returns the final data points per provider. Not filtered by provider, so we can fall back to the other ones in the response.
@cache
def get_elephant_history(region, bucket):
    fence = get_elephant_fence()
    params = {
        'region': region,
        'startTime': (bucket - fence).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'endTime': (bucket + fence).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    print(f"Accessing Elephant with {params}")
    response = requests.get(f"{get_elephant_url()}/carbon-intensity/history", params=params, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(f"Could not get carbon intensity from Elephant for {params}. Status: {response.status_code}. Response: {response.text}")

    # Estimations are skipped as a row is never updated again once it has a value. It waits for the final value instead.
    history = {}
    for entry in response.json():
        if entry.get('carbon_intensity') is not None and not entry.get('estimation'):
            history.setdefault(entry['provider'], []).append((datetime.fromisoformat(entry['time']), entry['carbon_intensity']))

    return history

def get_elephant_carbon_intensity(region, providers, measured_at, waited_long_enough):
    bucket_minute = measured_at.minute - measured_at.minute % get_elephant_fence_bucket_minutes()
    history = get_elephant_history(region, measured_at.replace(minute=bucket_minute, second=0, microsecond=0))
    preference = lambda provider: get_provider_preference(region, provider) # pylint: disable=unnecessary-lambda-assignment

    if waited_long_enough:
        if not history:
            return None
        points = history[min(history, key=preference)]
    else:
        # A missing provider in the response can just mean that it has not reported yet. So we do not fall back here, as the
        # row would then keep the value of another provider forever. Regions without the preferred provider start with their next best.


        # The API generates new data with a bit of a lag.
        # What we check here is that the lag has already caught up with the current time of the data to be backfilled.
        # This guarantees that our closest check later does not mistakenly choose a value that is technically in the fence
        # but a new value would still be coming soon that is closer to it.
        # The fence should be a fallback only and not be eager and to always be up to grab as soon as
        points = history.get(min(providers, key=preference), [])
        if not any(point_time >= measured_at for point_time, _ in points):
            return None

    _, value = min(points, key=lambda point: abs(point[0] - measured_at))  # get closest

    value = round(value)  # float -> int for DB

    if value <= 0: # should never be allowed by API and we need to check as DB has check constraint
        raise ValueError(f"Elephant returned 0 for region {region} measured at {measured_at}")

    # Must be an int as not all target columns can hold a float. Must also be > 0 due to the check constraints
    return value

def get_carbon_intensity(country_code, measured_at, created_at):

    if get_elephant_url() == 'testing':
        # If we are running tests we always return 1000
        return 1000

    if not country_code:
        return None

    country_code = country_code.upper()

    if providers := get_elephant_providers().get(country_code):
        waited_long_enough = datetime.now(timezone.utc) - created_at >= get_elephant_max_wait()

        carbon_intensity_g = get_elephant_carbon_intensity(country_code, providers, measured_at, waited_long_enough)
        if carbon_intensity_g is not None:
            return carbon_intensity_g

        if not waited_long_enough:
            return None # data point is likely still outstanding. Next run will try again

        print(f"Elephant has no data for {country_code} at {measured_at}. Using yearly average instead")

    return get_yearly_carbon_intensity(country_code)

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
    finally:
        DB().shutdown()
