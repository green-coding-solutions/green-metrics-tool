import calendar
import os
import pytest
import requests
from unittest.mock import Mock, patch
from datetime import datetime
from decimal import Decimal

GMT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))+'/../../'

from tests import test_functions as Tests
from lib.db import DB
from lib.carbon_intensity import (
    CarbonIntensityClient,
    CarbonIntensityServiceError,
    CarbonIntensityDataError,
    microseconds_to_iso8601,
    interpolate_carbon_intensity
)
from lib.phase_stats import build_and_store_phase_stats, get_carbon_intensity_for_timestamp


class TestCarbonIntensityClient:

    @patch('lib.carbon_intensity.GlobalConfig')
    def test_config_based_initialization(self, mock_global_config):
        # Test that client reads URL from config when not provided
        mock_config = Mock()
        mock_config.config = {
            'elephant': {
                'protocol': 'https',
                'host': 'example.com',
                'port': 9000
            }
        }
        mock_global_config.return_value = mock_config

        client = CarbonIntensityClient()
        assert client.base_url == "https://example.com:9000"

    @patch('lib.carbon_intensity.GlobalConfig')
    def test_config_based_initialization_defaults(self, mock_global_config):
        # Test that client uses defaults when config is empty
        mock_config = Mock()
        mock_config.config = {}
        mock_global_config.return_value = mock_config

        client = CarbonIntensityClient()
        assert client.base_url == "http://localhost:8000"

    def test_microseconds_to_iso8601(self):
        # Test timestamp conversion
        timestamp_us = 1727003400000000  # Some timestamp
        result = microseconds_to_iso8601(timestamp_us)
        # Just verify format is correct ISO 8601
        assert len(result) == 20
        assert result.endswith('Z')
        assert 'T' in result
        # Verify it's a valid timestamp that can be parsed back
        parsed = datetime.fromisoformat(result.replace('Z', '+00:00'))
        assert parsed is not None

    def test_interpolate_carbon_intensity_single_point(self):
        # Test with single data point
        carbon_data = [
            {"location": "DE", "time": "2024-09-22T10:00:00Z", "carbon_intensity": 185.0}
        ]
        timestamp_us = 1727003400000000  # 2024-09-22T10:50:00Z
        result = interpolate_carbon_intensity(timestamp_us, carbon_data)
        assert result == 185.0

    def test_interpolate_carbon_intensity_between_points(self):
        # Test interpolation between two points
        carbon_data = [
            {"location": "DE", "time": "2024-09-22T10:00:00Z", "carbon_intensity": 180.0},
            {"location": "DE", "time": "2024-09-22T11:00:00Z", "carbon_intensity": 200.0}
        ]
        # Calculate correct timestamp for 10:30:00 UTC
        mid_time = datetime(2024, 9, 22, 10, 30, 0)  # UTC time
        timestamp_us = int(calendar.timegm(mid_time.timetuple()) * 1_000_000)

        result = interpolate_carbon_intensity(timestamp_us, carbon_data)
        assert result == 190.0  # Linear interpolation: 180 + (200-180) * 0.5

    def test_interpolate_carbon_intensity_before_range(self):
        # Test with timestamp before data range
        carbon_data = [
            {"location": "DE", "time": "2024-09-22T11:00:00Z", "carbon_intensity": 185.0}
        ]
        timestamp_us = 1727001600000000  # 2024-09-22T10:20:00Z (before 11:00)
        result = interpolate_carbon_intensity(timestamp_us, carbon_data)
        assert result == 185.0  # Should return first value

    def test_interpolate_carbon_intensity_after_range(self):
        # Test with timestamp after data range
        carbon_data = [
            {"location": "DE", "time": "2024-09-22T10:00:00Z", "carbon_intensity": 185.0}
        ]
        timestamp_us = 1727007000000000  # 2024-09-22T11:50:00Z (after 10:00)
        result = interpolate_carbon_intensity(timestamp_us, carbon_data)
        assert result == 185.0  # Should return last value

    def test_interpolate_carbon_intensity_empty_data(self):
        # Test with empty data
        with pytest.raises(ValueError, match="No carbon intensity data available"):
            interpolate_carbon_intensity(1727003400000000, [])

    @patch('lib.carbon_intensity.requests.get')
    def test_carbon_intensity_client_success(self, mock_get):
        # Test successful API call
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            {"location": "DE", "time": "2024-09-22T10:00:00Z", "carbon_intensity": 185.0},
            {"location": "DE", "time": "2024-09-22T11:00:00Z", "carbon_intensity": 183.0}
        ]
        mock_get.return_value = mock_response

        client = CarbonIntensityClient("http://localhost:8000")
        result = client.get_carbon_intensity_history("DE", "2024-09-22T10:50:00Z", "2024-09-22T10:55:00Z")

        assert len(result) == 2
        assert result[0]['carbon_intensity'] == 185.0
        assert result[1]['carbon_intensity'] == 183.0

        mock_get.assert_called_once_with(
            "http://localhost:8000/carbon-intensity/history",
            params={
                'location': 'DE',
                'startTime': '2024-09-22T10:50:00Z',
                'endTime': '2024-09-22T10:55:00Z',
                'interpolate': 'true'
            },
            timeout=30
        )

    @patch('lib.carbon_intensity.requests.get')
    def test_carbon_intensity_client_network_error(self, mock_get):
        # Test network error handling
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        client = CarbonIntensityClient("http://localhost:8000")
        with pytest.raises(CarbonIntensityServiceError, match="Failed to fetch carbon intensity data"):
            client.get_carbon_intensity_history("DE", "2024-09-22T10:50:00Z", "2024-09-22T10:55:00Z")

    @patch('lib.carbon_intensity.requests.get')
    def test_carbon_intensity_client_invalid_response(self, mock_get):
        # Test invalid response handling
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"invalid": "response"}
        mock_get.return_value = mock_response

        client = CarbonIntensityClient("http://localhost:8000")
        with pytest.raises(CarbonIntensityDataError, match="Invalid response from carbon intensity service"):
            client.get_carbon_intensity_history("DE", "2024-09-22T10:50:00Z", "2024-09-22T10:55:00Z")


class TestGetCarbonIntensityForTimestamp:

    def test_static_mode_with_value(self):
        # Test static mode with I value
        sci = {'I': 334}
        result = get_carbon_intensity_for_timestamp(1727003400000000, sci, None)
        assert result == Decimal('334')

    def test_static_mode_missing_value(self):
        # Test static mode without I value
        sci = {}
        with pytest.raises(ValueError, match="No carbon intensity value available"):
            get_carbon_intensity_for_timestamp(1727003400000000, sci, None)

    def test_dynamic_mode(self):
        # Test dynamic mode with carbon data
        sci = {'I': 334}  # Should be ignored in dynamic mode
        carbon_data = [
            {"location": "DE", "time": "2024-09-22T10:00:00Z", "carbon_intensity": 185.0}
        ]
        result = get_carbon_intensity_for_timestamp(1727003400000000, sci, carbon_data)
        assert result == 185.0


class TestDynamicCarbonIntensityPhaseStats:

    @patch('lib.phase_stats.CarbonIntensityClient')
    def test_dynamic_carbon_intensity_integration(self, mock_client_class):
        # Test full integration with dynamic carbon intensity
        run_id = Tests.insert_run()
        Tests.import_machine_energy(run_id)

        # Add measurement start/end times to the run
        DB().query(
            "UPDATE runs SET start_measurement = %s, end_measurement = %s WHERE id = %s",
            (Tests.TEST_MEASUREMENT_START_TIME, Tests.TEST_MEASUREMENT_END_TIME, run_id)
        )

        # Mock the carbon intensity client
        mock_client = Mock()
        mock_client.get_carbon_intensity_history.return_value = [
            {"location": "DE", "time": "2024-09-22T10:00:00Z", "carbon_intensity": 200.0},
            {"location": "DE", "time": "2024-09-22T11:00:00Z", "carbon_intensity": 180.0}
        ]
        mock_client_class.return_value = mock_client

        # Test configuration with dynamic carbon intensity enabled
        sci = {'I': 334, 'N': 0.04106063}  # Static I should be ignored
        measurement_config = {
            'capabilities': {
                'measurement': {
                    'use_dynamic_carbon_intensity': True,
                    'carbon_intensity_location': 'DE'
                }
            }
        }

        build_and_store_phase_stats(run_id, sci, measurement_config)

        # Verify the carbon intensity client was called
        mock_client.get_carbon_intensity_history.assert_called_once()
        args = mock_client.get_carbon_intensity_history.call_args[0]
        assert args[0] == 'DE'  # location
        # args[1] and args[2] are start/end times in ISO format

        # Check that carbon stats were generated
        carbon_data = DB().fetch_all(
            'SELECT metric, value FROM phase_stats WHERE metric LIKE %s AND phase = %s',
            params=('%carbon%', '004_[RUNTIME]'),
            fetch_mode='dict'
        )

        assert len(carbon_data) > 0
        # Should have carbon data calculated with dynamic intensity (not static 334)

    def test_static_carbon_intensity_fallback(self):
        # Test fallback to static carbon intensity when dynamic is disabled
        run_id = Tests.insert_run()
        Tests.import_machine_energy(run_id)

        sci = {'I': 334}
        measurement_config = {
            'capabilities': {
                'measurement': {
                    'use_dynamic_carbon_intensity': False
                }
            }
        }

        build_and_store_phase_stats(run_id, sci, measurement_config)

        # Check that carbon stats were generated with static intensity
        carbon_data = DB().fetch_all(
            'SELECT metric, value FROM phase_stats WHERE metric LIKE %s AND phase = %s',
            params=('%carbon%', '004_[RUNTIME]'),
            fetch_mode='dict'
        )

        assert len(carbon_data) > 0

    def test_missing_location_error(self):
        # Test error when location is missing for dynamic mode
        run_id = Tests.insert_run()
        Tests.import_machine_energy(run_id)

        sci = {'I': 334}
        measurement_config = {
            'capabilities': {
                'measurement': {
                    'use_dynamic_carbon_intensity': True
                    # Missing carbon_intensity_location
                }
            }
        }

        with pytest.raises(ValueError, match="carbon_intensity_location is required"):
            build_and_store_phase_stats(run_id, sci, measurement_config)

    @patch('lib.phase_stats.CarbonIntensityClient')
    def test_service_error_propagation(self, mock_client_class):
        # Test that service errors are properly propagated
        run_id = Tests.insert_run()
        Tests.import_machine_energy(run_id)

        # Add measurement start/end times to the run
        DB().query(
            "UPDATE runs SET start_measurement = %s, end_measurement = %s WHERE id = %s",
            (Tests.TEST_MEASUREMENT_START_TIME, Tests.TEST_MEASUREMENT_END_TIME, run_id)
        )

        # Mock the client to raise an exception
        mock_client = Mock()
        mock_client.get_carbon_intensity_history.side_effect = CarbonIntensityServiceError("Service unavailable")
        mock_client_class.return_value = mock_client

        sci = {'I': 334}
        measurement_config = {
            'capabilities': {
                'measurement': {
                    'use_dynamic_carbon_intensity': True,
                    'carbon_intensity_location': 'DE'
                }
            }
        }

        with pytest.raises(CarbonIntensityServiceError, match="Service unavailable"):
            build_and_store_phase_stats(run_id, sci, measurement_config)
