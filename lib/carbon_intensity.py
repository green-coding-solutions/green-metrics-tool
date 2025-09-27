#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from datetime import datetime, timezone
from typing import List, Dict, Any
from io import StringIO
from lib.global_config import GlobalConfig
from lib.db import DB


class CarbonIntensityClient:
    def __init__(self, base_url: str = None):
        """
        Initialize carbon intensity client for Elephant service.

        Args:
            base_url: Base URL of the Elephant service. If None, reads from config.yml
        """
        if base_url is None:
            config = GlobalConfig().config
            dynamic_config = config.get('dynamic_grid_carbon_intensity', {})
            elephant_config = dynamic_config.get('elephant', {})
            protocol = elephant_config.get('protocol', 'http')
            host = elephant_config.get('host', 'localhost')
            port = elephant_config.get('port', 8000)
            base_url = f"{protocol}://{host}:{port}"

        self.base_url = base_url.rstrip('/')

    def get_carbon_intensity_history(self, location: str, start_time: str, end_time: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/carbon-intensity/history"
        params = {
            'location': location, # Location code (e.g., "DE", "ES-IB-MA")
            'startTime': start_time, # ISO 8601 format (e.g., "2025-09-22T10:50:00Z")
            'endTime': end_time, # ISO 8601 format (e.g., "2025-09-22T10:55:00Z")
            'interpolate': 'true' # we also want to get data points that are adjacent to the requested time range, to be ensure we always get at least one data point
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            raise ValueError(f"Expected list response from carbon intensity service, got {type(data)}")

        for item in data:
            if not all(key in item for key in ['location', 'time', 'carbon_intensity']):
                raise ValueError(f"Invalid carbon intensity data format: missing required fields in {item}")

        return data


def _get_run_data_and_phases(run_id):
    run_query = """
        SELECT phases, start_measurement, end_measurement
        FROM runs
        WHERE id = %s
    """
    run_data = DB().fetch_one(run_query, (run_id,))
    if not run_data or not run_data[0]:
        raise ValueError(f"Run {run_id} does not have phases data")

    phases, start_time_us, end_time_us = run_data
    return phases, start_time_us, end_time_us


def _create_measurement_metric(run_id, metric_name, detail_name, unit, sampling_rate):
    return DB().fetch_one('''
        INSERT INTO measurement_metrics (run_id, metric, detail_name, unit, sampling_rate_configured)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    ''', params=(run_id, metric_name, detail_name, unit, sampling_rate))[0]

# Defines for which timestamps a carbon intensity value is needed: run start/end & phase middles
def _get_base_timestamps(phases, start_time_us, end_time_us):
    timestamps = set()

    # Add overall run start and end times
    if start_time_us and end_time_us:
        timestamps.add(start_time_us)
        timestamps.add(end_time_us)

    # Add middle timestamp for each phase
    for phase in phases:
        middle_timestamp = (phase['start'] + phase['end']) // 2
        timestamps.add(middle_timestamp)

    return timestamps


def _bulk_insert_measurement_values(measurement_metric_id, value_timestamp_pairs):
    if not value_timestamp_pairs:
        return

    # For small datasets, use regular INSERT with multiple VALUES
    if len(value_timestamp_pairs) <= 10:
        values_to_insert = []
        for value, timestamp in value_timestamp_pairs:
            values_to_insert.extend([measurement_metric_id, int(value), timestamp])

        placeholders = ', '.join(['(%s, %s, %s)'] * len(value_timestamp_pairs))
        query = f"INSERT INTO measurement_values (measurement_metric_id, value, time) VALUES {placeholders}"
        DB().query(query, tuple(values_to_insert))
    # For larger datasets, use COPY FROM for better performance
    else:
        values_data = [(measurement_metric_id, int(value), timestamp)
                      for value, timestamp in value_timestamp_pairs]
        csv_data = '\n'.join([f"{row[0]},{row[1]},{row[2]}" for row in values_data])
        f = StringIO(csv_data)
        DB().copy_from(
            file=f,
            table='measurement_values',
            columns=['measurement_metric_id', 'value', 'time'],
            sep=','
        )
        f.close()


def store_static_carbon_intensity(run_id, static_value):
    phases, start_time_us, end_time_us = _get_run_data_and_phases(run_id)

    metric_name = 'grid_carbon_intensity_static'
    detail_name = '[CONFIG]'
    unit = 'gCO2e/kWh'
    sampling_rate = 0  # Static value has no sampling rate

    measurement_metric_id = _create_measurement_metric(
        run_id, metric_name, detail_name, unit, sampling_rate
    )

    carbon_intensity_value = int(float(static_value))

    # Calculate base timestamps, for which we definitely need a value:
    # start/end of run + middle of each phase
    timestamps = _get_base_timestamps(phases, start_time_us, end_time_us)

    value_timestamp_pairs = [(carbon_intensity_value, timestamp) for timestamp in timestamps]

    _bulk_insert_measurement_values(measurement_metric_id, value_timestamp_pairs)

    print(f"Stored static carbon intensity value {static_value} gCO2e/kWh at {len(timestamps)} timestamps (run start/end + phase middles)")


def store_dynamic_carbon_intensity(run_id, location):
    phases, start_time_us, end_time_us = _get_run_data_and_phases(run_id)
    start_time_iso = _microseconds_to_iso8601(start_time_us)
    end_time_iso = _microseconds_to_iso8601(end_time_us)

    carbon_client = CarbonIntensityClient()
    carbon_intensity_data = carbon_client.get_carbon_intensity_history(
        location, start_time_iso, end_time_iso
    )
    if not carbon_intensity_data:
        raise ValueError(
            f"No carbon intensity data received from service for location '{location}' "
            f"between {start_time_iso} and {end_time_iso}. The service returned an empty dataset."
        )

    values = [float(dp['carbon_intensity']) for dp in carbon_intensity_data]
    print(f"Retrieved {len(carbon_intensity_data)} API data points for {location}: "
            f"range {min(values):.1f}-{max(values):.1f} gCO2e/kWh")

    metric_name = 'grid_carbon_intensity_dynamic'
    detail_name = location
    unit = 'gCO2e/kWh'
    sampling_rate = _calculate_sampling_rate_from_data(carbon_intensity_data)

    measurement_metric_id = _create_measurement_metric(
        run_id, metric_name, detail_name, unit, sampling_rate
    )

    # Convert API data to format we need within GMT
    carbon_data_for_lookup = []
    for data_point in carbon_intensity_data:
        # Convert ISO timestamp to microseconds
        iso_time = data_point['time']
        dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
        timestamp_us = int(dt.timestamp() * 1_000_000)

        carbon_data_for_lookup.append({
            'timestamp_us': timestamp_us,
            'carbon_intensity': float(data_point['carbon_intensity'])
        })

    carbon_data_for_lookup.sort(key=lambda x: x['timestamp_us'])

    # Calculate base timestamps, for which we definitely need a value:
    # start/end of run + middle of each phase
    timestamps = _get_base_timestamps(phases, start_time_us, end_time_us)

    # Add any intermediate API data points that fall within measurement timeframe
    for data_point in carbon_data_for_lookup:
        timestamp_us = data_point['timestamp_us']
        if start_time_us <= timestamp_us <= end_time_us:
            timestamps.add(timestamp_us)

    value_timestamp_pairs = []
    if len(carbon_data_for_lookup) == 1:
        # If only one data point, use it for all timestamps
        carbon_intensity = carbon_data_for_lookup[0]['carbon_intensity']
        value_timestamp_pairs = [(carbon_intensity, timestamp) for timestamp in timestamps]
    else:
        # Convert timestamps to values using nearest data point logic
        for timestamp in timestamps:
            carbon_intensity = _get_carbon_intensity_at_timestamp(timestamp, carbon_data_for_lookup)
            value_timestamp_pairs.append((carbon_intensity, timestamp))

    _bulk_insert_measurement_values(measurement_metric_id, value_timestamp_pairs)

    unique_values = len(set(int(value) for value, _ in value_timestamp_pairs))
    print(f"Stored dynamic carbon intensity for location {location}: {len(value_timestamp_pairs)} timestamps, {unique_values} unique values")


# Find the data point with timestamp closest to target timestamp.
# Interpolation is not used on purpose here.
def _get_carbon_intensity_at_timestamp(timestamp_us: int, carbon_data: List[Dict[str, Any]]) -> float:
    closest_point = min(
        carbon_data,
        key=lambda point: abs(point['timestamp_us'] - timestamp_us)
    )

    return float(closest_point['carbon_intensity'])


def _calculate_sampling_rate_from_data(carbon_intensity_data: List[Dict[str, Any]]) -> int:
    if not carbon_intensity_data or len(carbon_intensity_data) < 2:
        return 0

    try:
        time1 = datetime.fromisoformat(carbon_intensity_data[0]['time'].replace('Z', '+00:00'))
        time2 = datetime.fromisoformat(carbon_intensity_data[1]['time'].replace('Z', '+00:00'))
        interval_seconds = abs((time2 - time1).total_seconds())
        sampling_rate = int(interval_seconds * 1000)
        return sampling_rate
    except (KeyError, ValueError, IndexError):
        return 0


def _microseconds_to_iso8601(timestamp_us: int) -> str:
    timestamp_seconds = timestamp_us / 1_000_000
    dt = datetime.fromtimestamp(timestamp_seconds, timezone.utc)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
