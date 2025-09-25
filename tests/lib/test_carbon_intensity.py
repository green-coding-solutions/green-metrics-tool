import calendar
import os
import pytest
import requests
from unittest.mock import Mock, patch
from datetime import datetime
from datetime import timezone

GMT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))+'/../../'

from tests import test_functions as Tests
from lib.db import DB
from lib.carbon_intensity import (
    CarbonIntensityClient,
    _microseconds_to_iso8601,
    _calculate_sampling_rate_from_data,
    _get_carbon_intensity_at_timestamp,
    get_carbon_intensity_data_for_run,
    store_static_carbon_intensity,
    store_dynamic_carbon_intensity,
    generate_carbon_intensity_timeseries_for_phase,
)

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

    def test__microseconds_to_iso8601(self):
        # Test timestamp conversion
        timestamp_us = 1727003400000000  # Some timestamp
        result = _microseconds_to_iso8601(timestamp_us)
        # Just verify format is correct ISO 8601
        assert len(result) == 20
        assert result.endswith('Z')
        assert 'T' in result
        # Verify it's a valid timestamp that can be parsed back
        parsed = datetime.fromisoformat(result.replace('Z', '+00:00'))
        assert parsed is not None

    def test__calculate_sampling_rate_from_data(self):
        # Test with 1 hour interval using API format with 'time' field
        carbon_data = [
            {"location": "DE", "time": "2025-09-23T10:00:00Z", "carbon_intensity": 253.0},
            {"location": "DE", "time": "2025-09-23T11:00:00Z", "carbon_intensity": 252.0}
        ]
        result = _calculate_sampling_rate_from_data(carbon_data)
        assert result == 3600000  # 1 hour = 3600 seconds = 3600000 ms

        # Test with 30 minute interval
        carbon_data_30min = [
            {"location": "DE", "time": "2025-09-23T10:00:00Z", "carbon_intensity": 253.0},
            {"location": "DE", "time": "2025-09-23T10:30:00Z", "carbon_intensity": 252.0}
        ]
        result = _calculate_sampling_rate_from_data(carbon_data_30min)
        assert result == 1800000  # 30 minutes = 1800 seconds = 1800000 ms

        # Test with empty data (should return fallback)
        result = _calculate_sampling_rate_from_data([])
        assert result == 300000  # 5 minutes fallback

        # Test with single data point (should return fallback)
        result = _calculate_sampling_rate_from_data([{"location": "DE", "time": "2025-09-23T10:00:00Z", "carbon_intensity": 253.0}])
        assert result == 300000  # 5 minutes fallback

        # Test with invalid data (should return fallback)
        result = _calculate_sampling_rate_from_data([{"invalid": "data"}, {"also": "invalid"}])
        assert result == 300000  # 5 minutes fallback

    def test__get_carbon_intensity_at_timestamp_single_point(self):
        # Test with single data point
        carbon_data = [
            {"location": "DE", "timestamp_us": int(datetime(2024, 9, 22, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000), "carbon_intensity": 185.0, "sampling_rate_ms": 300000}
        ]
        timestamp_us = 1727003400000000  # 2024-09-22T10:50:00Z
        result = _get_carbon_intensity_at_timestamp(timestamp_us, carbon_data)
        assert result == 185.0

    def test__get_carbon_intensity_at_timestamp_between_points(self):
        # Test nearest point selection between two points
        carbon_data = [
            {"location": "DE", "timestamp_us": int(datetime(2024, 9, 22, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000), "carbon_intensity": 180.0},
            {"location": "DE", "timestamp_us": int(datetime(2024, 9, 22, 11, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000), "carbon_intensity": 200.0}
        ]
        # Calculate correct timestamp for 10:30:00 UTC
        mid_time = datetime(2024, 9, 22, 10, 30, 0)  # UTC time
        timestamp_us = int(calendar.timegm(mid_time.timetuple()) * 1_000_000)

        result = _get_carbon_intensity_at_timestamp(timestamp_us, carbon_data)
        assert result == 180.0  # Nearest point: 10:30 is closer to 10:00 than 11:00

    def test__get_carbon_intensity_at_timestamp_before_range(self):
        # Test with timestamp before data range
        carbon_data = [
            {"location": "DE", "timestamp_us": int(datetime(2024, 9, 22, 11, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000), "carbon_intensity": 185.0}
        ]
        timestamp_us = 1727001600000000  # 2024-09-22T10:20:00Z (before 11:00)
        result = _get_carbon_intensity_at_timestamp(timestamp_us, carbon_data)
        assert result == 185.0  # Should return first value

    def test__get_carbon_intensity_at_timestamp_after_range(self):
        # Test with timestamp after data range
        carbon_data = [
            {"location": "DE", "timestamp_us": int(datetime(2024, 9, 22, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000), "carbon_intensity": 185.0}
        ]
        timestamp_us = 1727007000000000  # 2024-09-22T11:50:00Z (after 10:00)
        result = _get_carbon_intensity_at_timestamp(timestamp_us, carbon_data)
        assert result == 185.0  # Should return last value

    def test__get_carbon_intensity_at_timestamp_empty_data(self):
        # Test with empty data
        with pytest.raises(ValueError, match="min\\(\\) iterable argument is empty"):
            _get_carbon_intensity_at_timestamp(1727003400000000, [])

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
        with pytest.raises(requests.exceptions.RequestException):
            client.get_carbon_intensity_history("DE", "2024-09-22T10:50:00Z", "2024-09-22T10:55:00Z")

    @patch('lib.carbon_intensity.requests.get')
    def test_carbon_intensity_client_invalid_response(self, mock_get):
        # Test invalid response handling
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"invalid": "response"}
        mock_get.return_value = mock_response

        client = CarbonIntensityClient("http://localhost:8000")
        with pytest.raises(ValueError, match="Expected list response from carbon intensity service"):
            client.get_carbon_intensity_history("DE", "2024-09-22T10:50:00Z", "2024-09-22T10:55:00Z")


class TestGetCarbonIntensityDataForRun:

    def test_no_carbon_intensity_data(self):
        # Test with run that has no carbon intensity data
        run_id = Tests.insert_run()
        carbon_data, sampling_rate_ms = get_carbon_intensity_data_for_run(run_id)
        assert carbon_data is None
        assert sampling_rate_ms is None

    def test_with_dynamic_carbon_intensity_data(self):
        # Test with run that has dynamic carbon intensity data stored
        run_id = Tests.insert_run()

        # Insert mock carbon intensity metadata into measurement_metrics
        # This simulates data that would be stored during a run with dynamic carbon intensity
        metric_id = DB().fetch_one(
            "INSERT INTO measurement_metrics (run_id, metric, detail_name, unit, sampling_rate_configured) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (run_id, 'grid_carbon_intensity_dynamic', 'DE', 'gCO2e/kWh', 1000)
        )[0]

        # Insert actual carbon intensity values
        DB().query(
            "INSERT INTO measurement_values (measurement_metric_id, value, time) VALUES (%s, %s, %s)",
            (metric_id, 185, 1727003400000000)
        )

        carbon_data, sampling_rate_ms = get_carbon_intensity_data_for_run(run_id)

        # Should return the stored carbon intensity data
        assert carbon_data is not None
        assert len(carbon_data) > 0
        assert sampling_rate_ms == 1000  # Should match the sampling rate we inserted


class TestStoreCarbonIntensityAsMetrics:

    @pytest.fixture
    def run_with_measurement_times(self):
        """Fixture that creates a test run with measurement start/end times set."""
        run_id = Tests.insert_run()

        # Set measurement times (required for carbon intensity functions)
        DB().query(
            "UPDATE runs SET start_measurement = %s, end_measurement = %s WHERE id = %s",
            (Tests.TEST_MEASUREMENT_START_TIME, Tests.TEST_MEASUREMENT_END_TIME, run_id)
        )

        return run_id

    def test_store_carbon_intensity_static_value(self, run_with_measurement_times):
        # Test that static carbon intensity is stored when dynamic is not enabled
        run_id = run_with_measurement_times
        static_carbon_intensity = 250.5

        # Call the function with static value
        store_static_carbon_intensity(run_id, static_carbon_intensity)

        # Verify that measurement_metrics entry was created for static carbon intensity
        metric_result = DB().fetch_one(
            "SELECT metric, detail_name, unit FROM measurement_metrics WHERE run_id = %s",
            (run_id,)
        )

        assert metric_result is not None
        assert metric_result[0] == 'grid_carbon_intensity_static'
        assert metric_result[1] == '[CONFIG]'
        assert metric_result[2] == 'gCO2e/kWh'

        # Verify that static value was stored (should have up to 7 data points: start/end of run + middle of 5 phases, deduplicated)
        values_result = DB().fetch_all(
            """SELECT mv.value
               FROM measurement_values mv
               JOIN measurement_metrics mm ON mv.measurement_metric_id = mm.id
               WHERE mm.run_id = %s AND mm.metric = 'grid_carbon_intensity_static'""",
            (run_id,)
        )

        run_query = """
            SELECT phases, start_measurement, end_measurement
            FROM runs
            WHERE id = %s
        """
        run_data = DB().fetch_one(run_query, (run_id,))
        print(run_data)

        assert len(values_result) == 8  # 5 phases + 1 flow + start of run + end of run
        # All values should be the same static value
        for result in values_result:
            assert result[0] == 250 # 250.5 is converted to integer

    def test_store_carbon_intensity_dynamic_grid_enabled(self, run_with_measurement_times):
        # Test that dynamic grid carbon intensity is stored when enabled in measurement config
        run_id = run_with_measurement_times

        # Mock the carbon intensity API call
        # Use timestamps that align with the measurement timeframe (2024-12-24T13:33:10Z to 2024-12-24T13:41:00Z)
        with patch('lib.carbon_intensity.CarbonIntensityClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.get_carbon_intensity_history.return_value = [
                {"location": "DE", "time": "2024-12-24T13:32:00Z", "carbon_intensity": 185.0},  # Before start (for extrapolation)
                {"location": "DE", "time": "2024-12-24T13:35:00Z", "carbon_intensity": 190.0},  # Within timeframe
                {"location": "DE", "time": "2024-12-24T13:38:00Z", "carbon_intensity": 188.0},  # Within timeframe
                {"location": "DE", "time": "2024-12-24T13:42:00Z", "carbon_intensity": 183.0}   # After end (for extrapolation)
            ]

            # Call the function under test
            store_dynamic_carbon_intensity(run_id, 'DE')

        # Verify that measurement_metrics entry was created for dynamic carbon intensity
        metric_result = DB().fetch_one(
            "SELECT metric, detail_name, unit FROM measurement_metrics WHERE run_id = %s",
            (run_id,)
        )

        assert metric_result is not None
        assert metric_result[0] == 'grid_carbon_intensity_dynamic'
        assert metric_result[1] == 'DE'
        assert metric_result[2] == 'gCO2e/kWh'

        # Verify that measurement values were stored
        values_result = DB().fetch_all(
            """SELECT mv.value, mv.time
               FROM measurement_values mv
               JOIN measurement_metrics mm ON mv.measurement_metric_id = mm.id
               WHERE mm.run_id = %s AND mm.metric = 'grid_carbon_intensity_dynamic'
               ORDER BY mv.time""",
            (run_id,)
        )

        # Should have 4 data points: start boundary + 2 intermediate points + end boundary
        assert len(values_result) == 4
        # Values should be stored as integers
        # First point: interpolated start boundary (between 185.0 and 190.0)
        # Second point: 190.0 (intermediate point at 13:35:00)
        assert values_result[1][0] == 190
        # Third point: 188.0 (intermediate point at 13:38:00)
        assert values_result[2][0] == 188
        # Fourth point: interpolated end boundary (between 188.0 and 183.0)

    def test_store_carbon_intensity_dynamic_single_data_point(self, run_with_measurement_times):
        run_id = run_with_measurement_times

        # Mock the carbon intensity API call with only one data point within timeframe
        with patch('lib.carbon_intensity.CarbonIntensityClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.get_carbon_intensity_history.return_value = [
                {"location": "DE", "time": "2024-12-24T13:37:00Z", "carbon_intensity": 185.0}  # Within measurement timeframe
            ]

            # Call the function under test
            store_dynamic_carbon_intensity(run_id, 'DE')

        # Verify that measurement_metrics entry was created for dynamic carbon intensity
        metric_result = DB().fetch_one(
            "SELECT metric, detail_name, unit FROM measurement_metrics WHERE run_id = %s",
            (run_id,)
        )

        assert metric_result is not None
        assert metric_result[0] == 'grid_carbon_intensity_dynamic'
        assert metric_result[1] == 'DE'
        assert metric_result[2] == 'gCO2e/kWh'

        # Verify that measurement values were stored
        values_result = DB().fetch_all(
            """SELECT mv.value, mv.time
               FROM measurement_values mv
               JOIN measurement_metrics mm ON mv.measurement_metric_id = mm.id
               WHERE mm.run_id = %s AND mm.metric = 'grid_carbon_intensity_dynamic'
               ORDER BY mv.time""",
            (run_id,)
        )

        assert len(values_result) >= 2, "Dynamic carbon intensity requires at least 2 data points"

    def test_store_carbon_intensity_dynamic_data_outside_timeframe(self, run_with_measurement_times):
        # Test that dynamic carbon intensity properly handles data outside measurement timeframe using extrapolation
        run_id = run_with_measurement_times

        # Mock API data that is completely outside the measurement timeframe
        with patch('lib.carbon_intensity.CarbonIntensityClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.get_carbon_intensity_history.return_value = [
                {"location": "DE", "time": "2024-12-24T12:00:00Z", "carbon_intensity": 200.0},  # Well before start
                {"location": "DE", "time": "2024-12-24T12:30:00Z", "carbon_intensity": 210.0}   # Still before start
            ]

            # Call the function under test
            store_dynamic_carbon_intensity(run_id, 'DE')

        # Verify that measurement_metrics entry was created
        metric_result = DB().fetch_one(
            "SELECT metric, detail_name, unit FROM measurement_metrics WHERE run_id = %s",
            (run_id,)
        )

        assert metric_result is not None
        assert metric_result[0] == 'grid_carbon_intensity_dynamic'

        # Verify that measurement values were stored using extrapolation
        values_result = DB().fetch_all(
            """SELECT mv.value, mv.time
               FROM measurement_values mv
               JOIN measurement_metrics mm ON mv.measurement_metric_id = mm.id
               WHERE mm.run_id = %s AND mm.metric = 'grid_carbon_intensity_dynamic'
               ORDER BY mv.time""",
            (run_id,)
        )

        # Should have exactly 2 data points (start and end boundaries) since no intermediate points in timeframe
        assert len(values_result) == 2
        # Both values should be extrapolated from the trend in the API data (210 is higher than 200)

    def test_store_carbon_intensity_dynamic_missing_location(self, run_with_measurement_times):
        # Test error handling when dynamic method is called with None location
        run_id = run_with_measurement_times

        # Call the function with None location - should raise an exception or fail gracefully
        with pytest.raises(Exception):  # The method should fail when location is None
            store_dynamic_carbon_intensity(run_id, None)


class TestCarbonIntensityTimeseries:

    def test_generate_carbon_intensity_timeseries_for_phase(self):
        """Test generating carbon intensity timeseries for a phase"""
        # Sample carbon intensity data with microsecond timestamps
        carbon_data = [
            {"timestamp_us": int(datetime(2025, 9, 22, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000), "carbon_intensity": 185.0, "location": "DE"},
            {"timestamp_us": int(datetime(2025, 9, 22, 11, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000), "carbon_intensity": 190.0, "location": "DE"},
            {"timestamp_us": int(datetime(2025, 9, 22, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1_000_000), "carbon_intensity": 183.0, "location": "DE"}
        ]

        # Phase timeframe: 10:30 to 11:30 (90 minutes) in UTC
        phase_start_us = int(datetime(2025, 9, 22, 10, 30, 0, tzinfo=timezone.utc).timestamp() * 1_000_000)
        phase_end_us = int(datetime(2025, 9, 22, 11, 30, 0, tzinfo=timezone.utc).timestamp() * 1_000_000)

        # Generate timeseries with 30-minute intervals
        result = generate_carbon_intensity_timeseries_for_phase(
            phase_start_us, phase_end_us, carbon_data, sampling_rate_ms=30*60*1000
        )

        # Should generate points at 10:30, 11:00, 11:30
        assert len(result) == 3
        assert result[0]["timestamp_us"] == phase_start_us
        assert result[-1]["timestamp_us"] == phase_end_us

        # Values should be interpolated appropriately
        assert 185.0 <= result[0]["carbon_intensity"] <= 190.0  # Interpolated between 185 and 190
        assert result[1]["carbon_intensity"] == 190.0  # Exact match at 11:00
        assert 183.0 <= result[2]["carbon_intensity"] <= 190.0  # Interpolated between 190 and 183

    def test_get_carbon_intensity_timeseries_empty_data(self):
        """Test error handling with empty carbon data"""
        phase_start_us = int(datetime(2025, 9, 22, 10, 30, 0, tzinfo=timezone.utc).timestamp() * 1_000_000)
        phase_end_us = int(datetime(2025, 9, 22, 11, 30, 0, tzinfo=timezone.utc).timestamp() * 1_000_000)

        with pytest.raises(ValueError, match="No carbon intensity data available"):
            generate_carbon_intensity_timeseries_for_phase(phase_start_us, phase_end_us, [])

    def test_get_carbon_intensity_timeseries_invalid_timeframe(self):
        """Test error handling with invalid phase timeframe"""
        carbon_data = [{"time": "2025-09-22T10:00:00Z", "carbon_intensity": 185.0, "location": "DE"}]

        phase_start_us = int(datetime(2025, 9, 22, 11, 30, 0, tzinfo=timezone.utc).timestamp() * 1_000_000)
        phase_end_us = int(datetime(2025, 9, 22, 10, 30, 0, tzinfo=timezone.utc).timestamp() * 1_000_000)  # End before start

        with pytest.raises(ValueError, match="Invalid phase timeframe"):
            generate_carbon_intensity_timeseries_for_phase(phase_start_us, phase_end_us, carbon_data)
