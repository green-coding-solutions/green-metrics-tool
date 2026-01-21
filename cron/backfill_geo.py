#!/usr/bin/env python3

# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os
import fcntl

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

import ipaddress
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

    print(f"Current rows in DB where {table}.lat/lon is missing in last 30 days", fetch_geo_missing(table, count_only=True))

    updated_rows = update_geo_from_db_cache(table)

    print('Updated rows', updated_rows)

    print(f"Rows after db cached update where {table}.lat/lon is missing in last 30 days", fetch_geo_missing(table, count_only=True))

    data = fetch_geo_missing(table)
    backfill_geo_missing(table, data)

    print(f"Rows left after manual row-level update where {table}.lat/lon is missing in last 30 days", fetch_geo_missing(table, count_only=True))

def update_geo_from_db_cache(table):
    query = f"""
        WITH geo_missing AS (
            SELECT DISTINCT ON (from_table.id)
                from_table.id,
                ip.latitude,
                ip.longitude
            FROM {table} from_table
            JOIN ip_data ip
              ON
                  ip.ip_address = from_table.ip_address
                  AND ABS(EXTRACT(EPOCH FROM (from_table.created_at - ip.created_at::timestamp))) < EXTRACT(EPOCH FROM INTERVAL '30 DAYS')
            WHERE
                (from_table.latitude IS NULL OR from_table.longitude IS NULL)
                AND (from_table.carbon_intensity_g IS NULL) -- indicates it is not user set
            ORDER BY
                from_table.id,
                ABS(EXTRACT(EPOCH FROM (from_table.created_at - ip.created_at::timestamp))) ASC
        )
        UPDATE {table} from_table
        SET
            latitude = gm.latitude,
            longitude = gm.longitude
        FROM geo_missing gm
        WHERE from_table.id = gm.id
          AND gm.latitude IS NOT NULL
          AND gm.longitude IS NOT NULL
        RETURNING from_table.id, from_table.latitude, from_table.longitude;
    """

    return DB().fetch_all(query)

def fetch_geo_missing(table, count_only=False):

    if count_only:
        selection = 'COUNT(*)'
    else:
        selection = 'id, ip_address'

    query = f"""
        SELECT {selection}
        FROM {table} as from_table
        WHERE
            (from_table.longitude is NULL OR from_table.latitude IS NULL)
            AND from_table.carbon_intensity_g IS NULL -- indicates it is not user set
            AND from_table.ip_address IS NOT NULL
            AND created_at > NOW() - INTERVAL '30 DAYS'
    """
    data = DB().fetch_all(query)

    return data if data else []

def backfill_geo_missing(table, data):
    query = f"UPDATE {table} SET latitude = %s, longitude = %s WHERE id = %s"

    for row in data:
        row_id = row[0]
        row_ip = row[1]
        (latitude, longitude) = get_geo(row_ip) # since this function is cached we will not over-query API
        print('Filling', latitude, longitude, 'for id', row_id)
        DB().query(query, params=(latitude, longitude, row_id))


# The decorator will not work between workers, but since uvicorn_worker.UvicornWorker is using asyncIO it has some functionality between requests
@cached(cache=NoNoneOrNegativeValuesCache(maxsize=1024, ttl=86400)) # 24 hours
def get_geo(ip):
    ip_obj = ipaddress.ip_address(ip) # may raise a ValueError
    if ip_obj.is_private:
        error_helpers.log_error(f"Private IP was submitted to get_geo {ip}. This is normal in development, but should not happen in production.")
        return('52.53721666833642', '13.424863870661927')

    latitude, longitude = get_geo_ip_api_com(ip)

    if not latitude:
        latitude, longitude = get_geo_ipapi_co(ip)
    if not latitude:
        latitude, longitude = get_geo_ip_ipinfo(ip)
    if not latitude:
        raise RuntimeError(f"Could not get Geo-IP for {ip} after 3 tries")

    return (latitude, longitude)


def get_geo_ipapi_co(ip):

    print(f"Accessing https://ipapi.co/{ip}/json/")
    try:
        response = requests.get(f"https://ipapi.co/{ip}/json/", timeout=10)
    except Exception as exc: #pylint: disable=broad-exception-caught
        error_helpers.log_error('API request to ipapi.co failed ...', exception=exc)
        return (None, None)

    if response.status_code == 200:
        resp_data = response.json()

        if 'error' in resp_data or 'latitude' not in resp_data or 'longitude' not in resp_data:
            return (None, None)

        query = "INSERT INTO ip_data (ip_address, latitude, longitude, city, zip, org, country_code) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        DB().query(
            query=query,
            params=(ip, resp_data['latitude'], resp_data['longitude'], resp_data['city'], resp_data['postal'], resp_data['org'], resp_data['country_code'])
        )

        return (resp_data['latitude'], resp_data['longitude'])

    error_helpers.log_error(f"Could not get Geo-IP from ipapi.co for {ip}. Trying next ...", response=response)

    return (None, None)

def get_geo_ip_api_com(ip):

    print(f"Accessing http://ip-api.com/json/{ip}")
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=10)
    except Exception as exc: #pylint: disable=broad-exception-caught
        error_helpers.log_error('API request to ip-api.com failed ...', exception=exc)
        return (None, None)

    if response.status_code == 200:
        resp_data = response.json()

        if ('status' in resp_data and resp_data.get('status') == 'fail') or 'lat' not in resp_data or 'lon' not in resp_data:
            return (None, None)

        query = "INSERT INTO ip_data (ip_address, latitude, longitude, city, zip, org, country_code) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        DB().query(
            query=query,
            params=(ip, resp_data['lat'], resp_data['lon'], resp_data['city'], resp_data['zip'], resp_data['org'], resp_data['countryCode'])
        )
        return (resp_data['lat'], resp_data['lon'])

    error_helpers.log_error(f"Could not get Geo-IP from ip-api.com for {ip}. Trying next ...", response=response)

    return (None, None)

def get_geo_ip_ipinfo(ip):

    print(f"Accessing https://ipinfo.io/{ip}/json")
    try:
        response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=10)
    except Exception as exc: #pylint: disable=broad-exception-caught
        error_helpers.log_error('API request to ipinfo.io failed ...', exception=exc)
        return (None, None)

    if response.status_code == 200:
        resp_data = response.json()

        if 'bogon' in resp_data or 'loc' not in resp_data:
            return (None, None)

        latitude, longitude = resp_data['loc'].split(',')

        query = "INSERT INTO ip_data (ip_address, latitude, longitude, city, zip, org, country_code) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        DB().query(
            query=query,
            params=(ip, latitude, longitude, resp_data['city'], resp_data['postal'], resp_data['org'], resp_data['country'])
        )

        return (latitude, longitude)

    error_helpers.log_error(f"Could not get Geo-IP from ipinfo.io for {ip}. Trying next ...", response=response)

    return (None, None)

if __name__ == '__main__':
    try:
        GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/../manager-config.yml")

        lock_path = os.path.join(runtime_dir(), "gmt_backfill_geo.lock")
        with open(lock_path, "w", encoding='UTF-8') as lock_file:

            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB) # can raise BlockingIOError

            process('ci_measurements')
            process('hog_simplified_measurements')
            process('carbondb_data_raw')

            fcntl.flock(lock_file, fcntl.LOCK_UN) # release lock here only after successful processing. not in finally

    except Exception as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception=exc, machine=GlobalConfig().config['machine']['description'])
