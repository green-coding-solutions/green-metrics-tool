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
            elephant_config = config.get('elephant', {})
            protocol = elephant_config.get('protocol', 'http')
            host = elephant_config.get('host', 'localhost')
            port = elephant_config.get('port', 8000)
            base_url = f"{protocol}://{host}:{port}"

        self.base_url = base_url.rstrip('/')

    def get_carbon_intensity_history(self, location: str, start_time: str, end_time: str) -> List[Dict[str, Any]]:
        """
        Fetch carbon intensity history from Elephant service.

        Args:
            location: Location code (e.g., "DE", "ES-IB-MA")
            start_time: Start time in ISO 8601 format (e.g., "2025-09-22T10:50:00Z")
            end_time: End time in ISO 8601 format (e.g., "2025-09-22T10:55:00Z")

        Returns:
            List of carbon intensity data points:
            [{"location": "DE", "time": "2025-09-22T10:00:00Z", "carbon_intensity": 185.0}, ...]

        Raises:
            Exception: On any service error, network issue, or invalid response
        """
        url = f"{self.base_url}/carbon-intensity/history"
        params = {
            'location': location,
            'startTime': start_time,
            'endTime': end_time,
            'interpolate': 'true'
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


def store_static_carbon_intensity(run_id, static_value):
    """
    Store static carbon intensity value as a constant time series at multiple timestamps:
    - Start and end of measurement run to ensure graph looks good in frontend
    - Middle of each phase to enable carbon metrics calculation per phase

    Args:
        run_id: UUID of the run
        static_value: Static carbon intensity value from config (gCO2e/kWh)
    """
    # Get run phases data and overall start/end times
    run_query = """
        SELECT phases, start_measurement, end_measurement
        FROM runs
        WHERE id = %s
    """
    run_data = DB().fetch_one(run_query, (run_id,))
    if not run_data or not run_data[0]:
        raise ValueError(f"Run {run_id} does not have phases data")

    phases, start_time_us, end_time_us = run_data

    # Create measurement_metric entry for static carbon intensity
    metric_name = 'grid_carbon_intensity_static'
    detail_name = '[CONFIG]'
    unit = 'gCO2e/kWh'
    sampling_rate_configured = 0  # Static value has no sampling rate

    measurement_metric_id = DB().fetch_one('''
        INSERT INTO measurement_metrics (run_id, metric, detail_name, unit, sampling_rate_configured)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    ''', params=(run_id, metric_name, detail_name, unit, sampling_rate_configured))[0]

    # Convert static value to integer
    carbon_intensity_value = int(float(static_value))

    # Calculate timestamps: start/end of run + middle of each phase
    timestamps = set()

    # Add overall run start and end times
    if start_time_us and end_time_us:
        timestamps.add(start_time_us)
        timestamps.add(end_time_us)

    # Add middle timestamp for each phase
    for phase in phases:
        middle_timestamp = (phase['start'] + phase['end']) // 2
        timestamps.add(middle_timestamp)

    # Convert back to list for iteration
    timestamps = list(timestamps)

    # Insert static value for all timestamps
    values_to_insert = []
    for timestamp in timestamps:
        values_to_insert.extend([measurement_metric_id, carbon_intensity_value, timestamp])

    # Build dynamic query with correct number of placeholders
    placeholders = ', '.join(['(%s, %s, %s)'] * len(timestamps))
    query = f"INSERT INTO measurement_values (measurement_metric_id, value, time) VALUES {placeholders}"

    DB().query(query, tuple(values_to_insert))

    print(f"Stored static carbon intensity value {static_value} gCO2e/kWh at {len(timestamps)} timestamps (run start/end + phase middles)")


def store_dynamic_carbon_intensity(run_id, location):
    """
    Store dynamic carbon intensity data from API as time series.

    Args:
        run_id: UUID of the run
        location: Location code (e.g., "DE", "ES-IB-MA")
    """
    # Get run start and end times
    run_query = """
        SELECT start_measurement, end_measurement
        FROM runs
        WHERE id = %s
    """
    run_data = DB().fetch_one(run_query, (run_id,))
    if not run_data or not run_data[0] or not run_data[1]:
        raise ValueError(f"Run {run_id} does not have valid start_measurement and end_measurement times")

    start_time_us, end_time_us = run_data
    start_time_iso = _microseconds_to_iso8601(start_time_us)
    end_time_iso = _microseconds_to_iso8601(end_time_us)

    # Fetch carbon intensity data
    carbon_client = CarbonIntensityClient()
    carbon_intensity_data = carbon_client.get_carbon_intensity_history(
        location, start_time_iso, end_time_iso
    )

    if not carbon_intensity_data:
        raise ValueError(
            f"No carbon intensity data received from service for location '{location}' "
            f"between {start_time_iso} and {end_time_iso}. The service returned an empty dataset."
        )

    # Create measurement_metric entry for dynamic carbon intensity
    metric_name = 'grid_carbon_intensity_dynamic'
    detail_name = location
    unit = 'gCO2e/kWh'
    # Calculate sampling rate based on actual data intervals from API format
    sampling_rate_configured = _calculate_sampling_rate_from_data(carbon_intensity_data)

    measurement_metric_id = DB().fetch_one('''
        INSERT INTO measurement_metrics (run_id, metric, detail_name, unit, sampling_rate_configured)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    ''', params=(run_id, metric_name, detail_name, unit, sampling_rate_configured))[0]

    # Convert API data to format expected by _get_carbon_intensity_at_timestamp
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

    # Sort by timestamp for consistent processing
    carbon_data_for_lookup.sort(key=lambda x: x['timestamp_us'])

    # Prepare measurement values for bulk insert
    values_data = []

    # Always ensure we have data points at measurement start and end times
    # Get carbon intensity at measurement start time
    start_carbon_intensity = _get_carbon_intensity_at_timestamp(start_time_us, carbon_data_for_lookup)
    start_carbon_intensity_value = int(start_carbon_intensity)
    values_data.append((measurement_metric_id, start_carbon_intensity_value, start_time_us))

    # Get carbon intensity at measurement end time
    end_carbon_intensity = _get_carbon_intensity_at_timestamp(end_time_us, carbon_data_for_lookup)
    end_carbon_intensity_value = int(end_carbon_intensity)

    # Add intermediate data points that fall within measurement timeframe
    intermediate_points = []
    for data_point in carbon_data_for_lookup:
        timestamp_us = data_point['timestamp_us']
        # Only include points strictly within the timeframe (not at boundaries)
        if start_time_us < timestamp_us < end_time_us:
            carbon_intensity_value = int(float(data_point['carbon_intensity']))
            intermediate_points.append((measurement_metric_id, carbon_intensity_value, timestamp_us))

    # Sort intermediate points by time and add them
    intermediate_points.sort(key=lambda x: x[2])  # Sort by timestamp
    values_data.extend(intermediate_points)

    # Add end time point (ensure it's different from start time)
    if start_time_us != end_time_us:
        values_data.append((measurement_metric_id, end_carbon_intensity_value, end_time_us))


    if values_data:
        # Bulk insert measurement values using copy_from
        csv_data = '\n'.join([f"{row[0]},{row[1]},{row[2]}" for row in values_data])
        f = StringIO(csv_data)
        DB().copy_from(
            file=f,
            table='measurement_values',
            columns=['measurement_metric_id', 'value', 'time'],
            sep=','
        )
        f.close()

    print(f"Stored dynamic carbon intensity for location {location}: start={start_carbon_intensity} gCO2e/kWh, end={end_carbon_intensity} gCO2e/kWh, {len(intermediate_points)} intermediate points")


def _get_carbon_intensity_at_timestamp(timestamp_us: int, carbon_data: List[Dict[str, Any]]) -> float:
    """
    Get carbon intensity value for a specific timestamp using nearest data point.

    This function finds the carbon intensity at a given timestamp by:
    - Finding the data point with timestamp closest to the target timestamp
    - Returning the carbon intensity of that nearest data point

    Args:
        timestamp_us: Target timestamp in microseconds
        carbon_data: List of carbon intensity data points with 'timestamp_us' and 'carbon_intensity' fields
                    (guaranteed to be non-empty by calling functions)

    Returns:
        Carbon intensity value in gCO2e/kWh
    """
    # Find the data point with timestamp closest to target timestamp
    closest_point = min(
        carbon_data,
        key=lambda point: abs(point['timestamp_us'] - timestamp_us)
    )

    return float(closest_point['carbon_intensity'])


def _calculate_sampling_rate_from_data(carbon_intensity_data: List[Dict[str, Any]]) -> int:
    """
    Calculate sampling rate in milliseconds based on time intervals in carbon intensity data.

    Args:
        carbon_intensity_data: List of carbon intensity data points with 'time' field (API format)

    Returns:
        Sampling rate in milliseconds, or 300000 (5 minutes) as fallback

    Example:
        For data with 1 hour intervals: Returns 3600000 (1 hour in milliseconds)
    """
    if not carbon_intensity_data or len(carbon_intensity_data) < 2:
        return 300000

    try:
        time1 = datetime.fromisoformat(carbon_intensity_data[0]['time'].replace('Z', '+00:00'))
        time2 = datetime.fromisoformat(carbon_intensity_data[1]['time'].replace('Z', '+00:00'))
        interval_seconds = abs((time2 - time1).total_seconds())
        sampling_rate_configured = int(interval_seconds * 1000)
        return sampling_rate_configured
    except (KeyError, ValueError, IndexError):
        return 300000


def _microseconds_to_iso8601(timestamp_us: int) -> str:
    """
    Convert microsecond timestamp to ISO 8601 format.

    Args:
        timestamp_us: Timestamp in microseconds since epoch

    Returns:
        ISO 8601 formatted timestamp string (e.g., "2025-09-22T10:50:00Z")
    """
    timestamp_seconds = timestamp_us / 1_000_000
    dt = datetime.fromtimestamp(timestamp_seconds, timezone.utc)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
