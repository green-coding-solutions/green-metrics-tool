#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from datetime import datetime, timezone
from typing import List, Dict, Any
from io import StringIO
from lib import error_helpers
from lib.global_config import GlobalConfig
from lib.db import DB


class CarbonIntensityServiceError(Exception):
    """Raised when carbon intensity service request fails."""

class CarbonIntensityDataError(Exception):
    """Raised when carbon intensity service returns invalid data."""

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

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            if not isinstance(data, list):
                raise ValueError(f"Expected list response from carbon intensity service, got {type(data)}")

            for item in data:
                if not all(key in item for key in ['location', 'time', 'carbon_intensity']):
                    raise ValueError(f"Invalid carbon intensity data format: missing required fields in {item}")

            return data

        except requests.exceptions.RequestException as e:
            raise CarbonIntensityServiceError(f"Failed to fetch carbon intensity data: {e}") from e
        except (ValueError, KeyError) as e:
            raise CarbonIntensityDataError(f"Invalid response from carbon intensity service: {e}") from e



def get_carbon_intensity_data_for_run(run_id):
    """
    Get carbon intensity data for a run, automatically detecting dynamic vs static.

    Args:
        run_id: UUID of the run

    Returns:
        List of carbon intensity data points or None if no data found
    """
    # Auto-detect what carbon intensity data is available for this run
    # Check for both static and dynamic carbon intensity
    query = """
        SELECT metric, detail_name
        FROM measurement_metrics
        WHERE run_id = %s AND metric IN ('grid_carbon_intensity_static', 'grid_carbon_intensity_dynamic')
        LIMIT 1
    """
    result = DB().fetch_one(query, (run_id,))

    if result:
        metric, detail_name = result
        return _get_stored_carbon_intensity_data(run_id, metric, detail_name)

    return None


def interpolate_carbon_intensity(timestamp_us: int, carbon_data: List[Dict[str, Any]]) -> float:
    """
    Interpolate carbon intensity value for a specific timestamp.

    Args:
        timestamp_us: Target timestamp in microseconds
        carbon_data: List of carbon intensity data points from service

    Returns:
        Interpolated carbon intensity value in gCO2e/kWh

    Raises:
        ValueError: If carbon_data is empty or timestamp is outside range
    """
    if not carbon_data:
        raise ValueError("No carbon intensity data available for interpolation")

    target_time = datetime.fromtimestamp(timestamp_us / 1_000_000, timezone.utc).replace(tzinfo=None)

    # Convert carbon data times to datetime objects for comparison
    data_points = []
    for item in carbon_data:
        item_time = datetime.fromisoformat(item['time'].replace('Z', '+00:00')).replace(tzinfo=None)
        data_points.append((item_time, float(item['carbon_intensity'])))

    # Sort by time
    data_points.sort(key=lambda x: x[0])

    # Check if target is before first or after last data point
    if target_time <= data_points[0][0]:
        return data_points[0][1]
    if target_time >= data_points[-1][0]:
        return data_points[-1][1]

    # Find surrounding data points for interpolation
    for i in range(len(data_points) - 1):
        time1, value1 = data_points[i]
        time2, value2 = data_points[i + 1]

        if time1 <= target_time <= time2:
            # Linear interpolation
            time_diff = (time2 - time1).total_seconds()
            if time_diff == 0:
                return value1

            target_diff = (target_time - time1).total_seconds()
            ratio = target_diff / time_diff

            return value1 + (value2 - value1) * ratio

    raise ValueError(f"Could not interpolate carbon intensity for timestamp {target_time}")


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


def store_static_carbon_intensity(run_id, static_value):
    """
    Store static carbon intensity value as a constant time series.

    Args:
        run_id: UUID of the run
        static_value: Static carbon intensity value from config (gCO2e/kWh)
    """
    # Get run start and end times
    run_query = """
        SELECT start_measurement, end_measurement
        FROM runs
        WHERE id = %s
    """
    run_data = DB().fetch_one(run_query, (run_id,))
    if not run_data or not run_data[0] or not run_data[1]:
        error_helpers.log_error(f"Run {run_id} does not have valid start_measurement and end_measurement times", run_id=run_id)
        return

    start_time_us, end_time_us = run_data

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

    # Convert static value to integer (multiply by 1000 for precision)
    carbon_intensity_value = int(float(static_value) * 1000)

    # Store as constant time series: same value at start and end times
    values_data = [
        f"{measurement_metric_id},{carbon_intensity_value},{start_time_us}",
        f"{measurement_metric_id},{carbon_intensity_value},{end_time_us}"
    ]

    csv_data = '\n'.join(values_data)
    f = StringIO(csv_data)
    DB().copy_from(
        file=f,
        table='measurement_values',
        columns=['measurement_metric_id', 'value', 'time'],
        sep=','
    )
    f.close()

    print(f"Stored static carbon intensity value {static_value} gCO2e/kWh as constant time series")


def store_dynamic_carbon_intensity(run_id, grid_carbon_intensity_location):
    """
    Store dynamic carbon intensity data from API as time series.

    Args:
        run_id: UUID of the run
        grid_carbon_intensity_location: Location code (e.g., "DE", "ES-IB-MA")
    """
    # Get run start and end times
    run_query = """
        SELECT start_measurement, end_measurement
        FROM runs
        WHERE id = %s
    """
    run_data = DB().fetch_one(run_query, (run_id,))
    if not run_data or not run_data[0] or not run_data[1]:
        error_helpers.log_error(f"Run {run_id} does not have valid start_measurement and end_measurement times", run_id=run_id)
        return

    start_time_us, end_time_us = run_data
    start_time_iso = _microseconds_to_iso8601(start_time_us)
    end_time_iso = _microseconds_to_iso8601(end_time_us)

    # Fetch carbon intensity data
    carbon_client = CarbonIntensityClient()
    carbon_intensity_data = carbon_client.get_carbon_intensity_history(
        grid_carbon_intensity_location, start_time_iso, end_time_iso
    )

    if not carbon_intensity_data:
        error_helpers.log_error("No carbon intensity data received from service", run_id=run_id)
        return

    # Create measurement_metric entry for dynamic carbon intensity
    metric_name = 'grid_carbon_intensity_dynamic'
    detail_name = grid_carbon_intensity_location
    unit = 'gCO2e/kWh'
    # Estimate sampling rate as 5 minutes (300000ms) based on typical grid data frequency
    sampling_rate_configured = 300000

    measurement_metric_id = DB().fetch_one('''
        INSERT INTO measurement_metrics (run_id, metric, detail_name, unit, sampling_rate_configured)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    ''', params=(run_id, metric_name, detail_name, unit, sampling_rate_configured))[0]

    # Prepare measurement values for bulk insert
    values_data = []
    for data_point in carbon_intensity_data:
        # Convert ISO timestamp to microseconds
        iso_time = data_point['time']
        dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
        timestamp_us = int(dt.timestamp() * 1_000_000)

        # Convert carbon intensity to integer (multiply by 1000 for precision)
        carbon_intensity_value = int(float(data_point['carbon_intensity']) * 1000)

        values_data.append(f"{measurement_metric_id},{carbon_intensity_value},{timestamp_us}")

    if values_data:
        # Bulk insert measurement values
        csv_data = '\n'.join(values_data)
        f = StringIO(csv_data)
        DB().copy_from(
            file=f,
            table='measurement_values',
            columns=['measurement_metric_id', 'value', 'time'],
            sep=','
        )
        f.close()

    print(f"Stored {len(values_data)} dynamic carbon intensity data points for location {grid_carbon_intensity_location}")


def _get_stored_carbon_intensity_data(run_id, metric_name, detail_name):
    """
    Retrieve stored carbon intensity data from measurement_metrics for a run.

    Args:
        run_id: UUID of the run
        metric_name: Either 'grid_carbon_intensity_static' or 'grid_carbon_intensity_dynamic'
        detail_name: '[CONFIG]' for static, location code for dynamic (e.g., "DE", "ES-IB-MA")

    Returns:
        List of carbon intensity data points or None if no data found
    """
    query = """
        SELECT mv.time, mv.value
        FROM measurement_values mv
        JOIN measurement_metrics mm ON mv.measurement_metric_id = mm.id
        WHERE mm.run_id = %s
        AND mm.metric = %s
        AND mm.detail_name = %s
        ORDER BY mv.time ASC
    """
    results = DB().fetch_all(query, (run_id, metric_name, detail_name))

    if not results:
        return None

    # Convert stored data back to the format expected by interpolate_carbon_intensity
    carbon_data = []
    for timestamp_us, value_int in results:
        # Convert back from integer storage (divide by 1000 to restore decimal precision)
        carbon_intensity = float(value_int) / 1000.0
        # Convert timestamp to ISO format for consistency
        dt = datetime.fromtimestamp(timestamp_us / 1_000_000, timezone.utc)
        iso_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        carbon_data.append({
            'time': iso_time,
            'carbon_intensity': carbon_intensity,
            'location': detail_name
        })

    return carbon_data
