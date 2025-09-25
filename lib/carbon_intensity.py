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
    """
    Fetch run data including phases and measurement times.

    Args:
        run_id: UUID of the run

    Returns:
        tuple: (phases, start_time_us, end_time_us)

    Raises:
        ValueError: If run data is invalid or missing
    """
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
    """
    Create a measurement metric entry in the database.

    Args:
        run_id: UUID of the run
        metric_name: Name of the metric
        detail_name: Detail/source name for the metric
        unit: Unit of measurement
        sampling_rate: Configured sampling rate

    Returns:
        int: measurement_metric_id
    """
    return DB().fetch_one('''
        INSERT INTO measurement_metrics (run_id, metric, detail_name, unit, sampling_rate_configured)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    ''', params=(run_id, metric_name, detail_name, unit, sampling_rate))[0]


def _get_base_timestamps(phases, start_time_us, end_time_us):
    """
    Defines for which timestamps a carbon intensity value is needed:
    - run start/end
    - phase middles

    Args:
        phases: List of phase dictionaries
        start_time_us: Run start time in microseconds
        end_time_us: Run end time in microseconds

    Returns:
        set: Set of timestamps
    """
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
    """
    Efficiently insert measurement values using the most appropriate method.

    Args:
        measurement_metric_id: ID of the measurement metric
        value_timestamp_pairs: List of (value, timestamp) tuples
    """
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
    else:
        # For larger datasets, use COPY FROM for better performance
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
    """
    Store static carbon intensity value as a constant time series at multiple timestamps:
    - Start and end of measurement run to ensure graph looks good in frontend
    - Middle of each phase to enable carbon metrics calculation per phase

    Args:
        run_id: UUID of the run
        static_value: Static carbon intensity value from config (gCO2e/kWh)
    """
    phases, start_time_us, end_time_us = _get_run_data_and_phases(run_id)

    metric_name = 'grid_carbon_intensity_static'
    detail_name = '[CONFIG]'
    unit = 'gCO2e/kWh'
    sampling_rate = 0  # Static value has no sampling rate

    measurement_metric_id = _create_measurement_metric(
        run_id, metric_name, detail_name, unit, sampling_rate
    )

    # Convert static value to integer
    carbon_intensity_value = int(float(static_value))

    # Calculate timestamps: start/end of run + middle of each phase
    timestamps = _get_base_timestamps(phases, start_time_us, end_time_us)

    # Prepare value-timestamp pairs for bulk insert
    value_timestamp_pairs = [(carbon_intensity_value, timestamp) for timestamp in timestamps]

    # Insert static value for all timestamps
    _bulk_insert_measurement_values(measurement_metric_id, value_timestamp_pairs)

    print(f"Stored static carbon intensity value {static_value} gCO2e/kWh at {len(timestamps)} timestamps (run start/end + phase middles)")


def store_dynamic_carbon_intensity(run_id, location):
    """
    Store dynamic carbon intensity data from API as time series, ensuring coverage per phase.
    Uses nearest data point logic for timestamps where API data may be sparse.

    Args:
        run_id: UUID of the run
        location: Grid zone code (e.g., "DE", "CH", "ES-IB-MA")
    """
    phases, start_time_us, end_time_us = _get_run_data_and_phases(run_id)
    start_time_iso = _microseconds_to_iso8601(start_time_us)
    end_time_iso = _microseconds_to_iso8601(end_time_us)

    # Fetch dynamic carbon intensity data for the relevant time frame
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

    # Sort by timestamp for consistent processing
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

    # Bulk insert measurement values
    _bulk_insert_measurement_values(measurement_metric_id, value_timestamp_pairs)

    unique_values = len(set(int(value) for value, _ in value_timestamp_pairs))
    print(f"Stored dynamic carbon intensity for location {location}: {len(value_timestamp_pairs)} timestamps, {unique_values} unique values")


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
        Sampling rate in milliseconds, or 0 as fallback

    Example:
        For data with 1 hour intervals: Returns 3600000 (1 hour in milliseconds)
    """
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
