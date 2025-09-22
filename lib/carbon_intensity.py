#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from datetime import datetime
from typing import List, Dict, Any
from lib import error_helpers
from lib.global_config import GlobalConfig


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
            error_helpers.log_error(f"Carbon intensity service request failed: {e}")
            raise CarbonIntensityServiceError(f"Failed to fetch carbon intensity data: {e}") from e
        except (ValueError, KeyError) as e:
            error_helpers.log_error(f"Invalid carbon intensity service response: {e}")
            raise CarbonIntensityDataError(f"Invalid response from carbon intensity service: {e}") from e


def microseconds_to_iso8601(timestamp_us: int) -> str:
    """
    Convert microsecond timestamp to ISO 8601 format.

    Args:
        timestamp_us: Timestamp in microseconds since epoch

    Returns:
        ISO 8601 formatted timestamp string (e.g., "2025-09-22T10:50:00Z")
    """
    timestamp_seconds = timestamp_us / 1_000_000
    dt = datetime.utcfromtimestamp(timestamp_seconds)
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


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

    target_time = datetime.utcfromtimestamp(timestamp_us / 1_000_000).replace(tzinfo=None)

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
