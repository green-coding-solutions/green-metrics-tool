import shutil
import pandas
import pytest
import requests
import tempfile

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from metric_providers.carbon.intensity.electricitymaps.machine.provider import (
    CarbonIntensityElectricityMapsMachineProvider,
    API_PAST_URL,
    API_FUTURE_URL,
)
from metric_providers.base import MetricProviderConfigurationError

GMT_METRICS_DIR = Path(tempfile.mkdtemp(prefix='green-metrics-tool-metrics-'))

FIXED_TOKEN = 'test-token-123'
FIXED_REGION = 'DE'
FIXED_TIME = '2026-04-28T12:00:00Z'
FIXED_VALUE = 42

PAST_RECORD = {'datetime': FIXED_TIME, 'carbonIntensity': FIXED_VALUE}
PAST_RESPONSE = {'data': [PAST_RECORD]}
EMPTY_RESPONSE = {'data': []}


@pytest.fixture(autouse=True, scope='module')
def setup_metrics_dir():
    GMT_METRICS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(GMT_METRICS_DIR)



def make_provider(**kwargs):
    defaults = {'region': FIXED_REGION, 'token': FIXED_TOKEN, 'folder': GMT_METRICS_DIR, 'skip_check': True}
    defaults.update(kwargs)
    return CarbonIntensityElectricityMapsMachineProvider(**defaults)


def make_response(json_data=None, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data if json_data is not None else EMPTY_RESPONSE
    mock.text = str(json_data)
    mock.close.return_value = None
    # Support context-manager usage: `with requests.get(...) as response:`
    mock.__enter__ = MagicMock(return_value=mock)
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def profiled_provider(**kwargs):
    provider = make_provider(**kwargs)
    provider.start_profiling()
    provider.stop_profiling()
    return provider


# --- Constructor / config validation ---

def test_missing_region_raises():
    with pytest.raises(MetricProviderConfigurationError, match='region'):
        CarbonIntensityElectricityMapsMachineProvider(region='', token=FIXED_TOKEN, folder=GMT_METRICS_DIR, skip_check=True)


def test_missing_token_raises():
    with pytest.raises(MetricProviderConfigurationError, match='token'):
        CarbonIntensityElectricityMapsMachineProvider(region=FIXED_REGION, token='', folder=GMT_METRICS_DIR, skip_check=True)


# --- check_system ---

def test_check_system_success():
    provider = make_provider()
    with patch('requests.get', return_value=make_response(PAST_RESPONSE)):
        provider.check_system()


def test_check_system_sends_auth_token():
    provider = make_provider()
    with patch('requests.get', return_value=make_response(PAST_RESPONSE)) as mock_get:
        provider.check_system()
    headers = mock_get.call_args[1]['headers']
    assert headers['auth-token'] == FIXED_TOKEN


def test_check_system_401_raises():
    provider = make_provider()
    with patch('requests.get', return_value=make_response(status_code=401)):
        with pytest.raises(MetricProviderConfigurationError, match='token'):
            provider.check_system()


def test_check_system_403_raises():
    provider = make_provider()
    with patch('requests.get', return_value=make_response(status_code=403)):
        with pytest.raises(MetricProviderConfigurationError, match='token'):
            provider.check_system()


def test_check_system_network_failure_raises():
    provider = make_provider()
    with patch('requests.get', side_effect=requests.RequestException('timeout')):
        with pytest.raises(MetricProviderConfigurationError, match='could not be reached'):
            provider.check_system()


# --- _read_metrics: normal path ---

def test_read_metrics_returns_fixed_value():
    provider = profiled_provider()
    with patch('requests.get', return_value=make_response(PAST_RESPONSE)):
        df = provider._read_metrics()
    assert not df.empty
    assert df['value'].iloc[0] == FIXED_VALUE


def test_read_metrics_uses_past_url():
    provider = profiled_provider()
    with patch('requests.get', return_value=make_response(PAST_RESPONSE)) as mock_get:
        provider._read_metrics()
    assert mock_get.call_args[0][0] == API_PAST_URL


def test_read_metrics_uses_v4_urls():
    assert '/v4/' in API_PAST_URL
    assert '/v4/' in API_FUTURE_URL


def test_read_metrics_sends_auth_token():
    provider = profiled_provider()
    with patch('requests.get', return_value=make_response(PAST_RESPONSE)) as mock_get:
        provider._read_metrics()
    headers = mock_get.call_args[1]['headers']
    assert headers['auth-token'] == FIXED_TOKEN


def test_read_metrics_sends_region_as_zone():
    provider = profiled_provider()
    with patch('requests.get', return_value=make_response(PAST_RESPONSE)) as mock_get:
        provider._read_metrics()
    params = mock_get.call_args[1]['params']
    assert params['zone'] == FIXED_REGION


def test_read_metrics_detail_name_is_electricity_maps():
    provider = profiled_provider()
    with patch('requests.get', return_value=make_response(PAST_RESPONSE)):
        df = provider._read_metrics()
    assert df['provider'].iloc[0] == 'electricity_maps'


# --- _read_metrics: fallback to forecast ---

def _make_get_with_fallback(fallback_json):
    def side_effect(url, **_kwargs):
        if url == API_PAST_URL:
            return make_response(EMPTY_RESPONSE)
        return make_response(fallback_json)
    return side_effect


def test_empty_past_data_triggers_forecast_fallback():
    provider = profiled_provider()
    fallback = {'data': [{'datetime': FIXED_TIME, 'carbonIntensity': 99}]}
    with patch('requests.get', side_effect=_make_get_with_fallback(fallback)) as mock_get:
        df = provider._read_metrics()
    urls_called = [c[0][0] for c in mock_get.call_args_list]
    assert API_FUTURE_URL in urls_called
    assert not df.empty


def test_empty_past_data_accepts_v4_forecast_payload():
    provider = profiled_provider()
    fallback = {'forecast': [{'datetime': FIXED_TIME, 'carbonIntensity': 99}]}

    with patch('requests.get', side_effect=_make_get_with_fallback(fallback)):
        df = provider._read_metrics()

    assert not df.empty
    assert df['value'].iloc[0] == 99


def test_fallback_sends_only_zone_param():
    provider = profiled_provider()
    fallback = {'data': [{'datetime': FIXED_TIME, 'carbonIntensity': 55}]}
    with patch('requests.get', side_effect=_make_get_with_fallback(fallback)) as mock_get:
        provider._read_metrics()
    fallback_call = next(c for c in mock_get.call_args_list if c[0][0] == API_FUTURE_URL)
    params = fallback_call[1]['params']
    assert 'zone' in params
    assert 'start' not in params
    assert 'end' not in params


def test_fallback_http_error_returns_none():
    provider = profiled_provider()

    def side_effect(url, **_kwargs):
        if url == API_PAST_URL:
            return make_response(EMPTY_RESPONSE)
        return make_response(status_code=503)

    with patch('requests.get', side_effect=side_effect):
        result = provider._read_metrics()
    assert isinstance(result, pandas.DataFrame) and result.empty
    assert provider._error_string != ''


# --- _read_metrics: error paths ---

def test_http_error_returns_none_and_logs():
    provider = profiled_provider()
    with patch('requests.get', return_value=make_response(status_code=500)):
        result = provider._read_metrics()
    assert isinstance(result, pandas.DataFrame) and result.empty
    assert '500' in provider._error_string


def test_network_failure_returns_none_and_logs():
    provider = profiled_provider()
    with patch('requests.get', side_effect=requests.RequestException('timeout')):
        result = provider._read_metrics()
    assert isinstance(result, pandas.DataFrame) and result.empty

    assert provider._error_string != ''


# --- _read_metrics: missing start/end times ---

def test_read_metrics_without_profiling_raises():
    provider = make_provider()
    with pytest.raises(RuntimeError, match='start_profiling'):
        provider._read_metrics()


# --- closest-entry fallback (no records in time window) ---

def test_out_of_window_entry_used_as_closest():
    provider = profiled_provider()
    # Provide a record that is outside the start/end window — should still be returned as closest
    out_of_window = {'data': [{'datetime': '2020-01-01T00:00:00Z', 'carbonIntensity': 77}]}
    with patch('requests.get', return_value=make_response(out_of_window)):
        df = provider._read_metrics()
    assert not df.empty
    assert df['value'].iloc[0] == 77


# --- multiple records ---

def test_multiple_records_sorted_by_time():
    provider = make_provider()
    # Set fixed window that brackets both test records so neither is filtered out
    provider._start_time = datetime(2026, 4, 28, 11, 59, 0, tzinfo=timezone.utc)
    provider._end_time = datetime(2026, 4, 28, 12, 11, 0, tzinfo=timezone.utc)
    records = {
        'data': [
            {'datetime': '2026-04-28T12:10:00Z', 'carbonIntensity': 80},
            {'datetime': '2026-04-28T12:00:00Z', 'carbonIntensity': 40},
        ]
    }
    with patch('requests.get', return_value=make_response(records)):
        df = provider._read_metrics()
    assert df['time'].is_monotonic_increasing
    assert df['value'].iloc[0] == 40
    assert df['value'].iloc[1] == 80


# --- sampling_rate expansion ---

def test_read_metrics_expands_to_sampling_rate():
    # Regression test: expand_to_sampling_rate accesses _start_time/_end_time via
    # a module-level function; previously used double-underscore names which caused
    # AttributeError when sampling_rate > 0 due to Python's name-mangling rules.
    provider = make_provider(sampling_rate=1000)  # 1 s in ms
    provider._start_time = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
    provider._end_time   = datetime(2026, 4, 28, 12, 0, 3, tzinfo=timezone.utc)

    records = {'data': [{'datetime': '2026-04-28T12:00:00Z', 'carbonIntensity': 42}]}
    with patch('requests.get', return_value=make_response(records)):
        df = provider._read_metrics()

    # 3-second window at 1 s steps → 4 rows (0 s, 1 s, 2 s, 3 s)
    assert len(df) == 4
    assert (df['value'] == 42).all()
    assert df['time'].is_monotonic_increasing
