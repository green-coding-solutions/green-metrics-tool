import shutil
import pytest
import requests
import uuid

from pathlib import Path
from unittest.mock import patch, MagicMock

from metric_providers.carbon.intensity.elephant.machine.provider import CarbonIntensityElephantMachineProvider
from metric_providers.base import MetricProviderConfigurationError

GMT_METRICS_DIR = Path('/tmp/green-metrics-tool/metrics')

ELEPHANT_CONFIG = {'host': 'localhost', 'port': 9999, 'protocol': 'http'}
BASE_URL = 'http://localhost:9999'

FIXED_TIME = '2026-04-28T12:00:00Z'
FIXED_VALUE = 42
FIXED_PROVIDER = 'test_de'

HISTORY_RECORD = [{'time': FIXED_TIME, 'carbon_intensity': FIXED_VALUE, 'provider': FIXED_PROVIDER}]


@pytest.fixture(autouse=True, scope='module')
def setup_metrics_dir():
    GMT_METRICS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(GMT_METRICS_DIR)


def make_provider(**kwargs):
    defaults = {'region': 'DE', 'elephant': ELEPHANT_CONFIG, 'folder': GMT_METRICS_DIR, 'skip_check': True}
    defaults.update(kwargs)
    return CarbonIntensityElephantMachineProvider(**defaults)


def make_response(json_data=None, status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data if json_data is not None else []
    mock.text = str(json_data)
    mock.close.return_value = None
    return mock


def profiled_provider(**kwargs):
    provider = make_provider(**kwargs)
    provider.start_profiling()
    provider.stop_profiling()
    return provider


# --- Constructor / config validation ---

def test_missing_region_raises():
    with pytest.raises(MetricProviderConfigurationError, match='region'):
        CarbonIntensityElephantMachineProvider(region='', elephant=ELEPHANT_CONFIG, folder=GMT_METRICS_DIR, skip_check=True)


def test_missing_elephant_block_raises():
    with pytest.raises(MetricProviderConfigurationError, match='elephant'):
        CarbonIntensityElephantMachineProvider(region='DE', elephant=None, folder=GMT_METRICS_DIR, skip_check=True)


def test_incomplete_elephant_config_raises():
    with pytest.raises(MetricProviderConfigurationError):
        CarbonIntensityElephantMachineProvider(region='DE', elephant={'host': 'localhost'}, folder=GMT_METRICS_DIR, skip_check=True)


# --- check_system ---

def test_check_system_success():
    provider = make_provider()
    with patch('requests.get', return_value=make_response()) as mock_get:
        provider.check_system()
    mock_get.assert_called_once_with(BASE_URL, timeout=10)


def test_check_system_failure_raises():
    provider = make_provider()
    with patch('requests.get', side_effect=requests.RequestException('connection refused')):
        with pytest.raises(MetricProviderConfigurationError, match='could not be reached'):
            provider.check_system()


# --- _read_metrics: normal path ---

def test_read_metrics_returns_fixed_value():
    provider = profiled_provider()
    with patch('requests.get', return_value=make_response(HISTORY_RECORD)):
        df = provider._read_metrics()
    assert not df.empty
    assert df['value'].iloc[0] == FIXED_VALUE
    assert df['provider'].iloc[0] == FIXED_PROVIDER


def test_read_metrics_url_and_params():
    provider = profiled_provider()
    with patch('requests.get', return_value=make_response(HISTORY_RECORD)) as mock_get:
        provider._read_metrics()
    call_kwargs = mock_get.call_args
    assert call_kwargs[0][0] == f'{BASE_URL}/carbon-intensity/history'
    assert call_kwargs[1]['params']['region'] == 'DE'
    assert call_kwargs[1]['params']['update'] == 'true'


def test_read_metrics_with_provider_filter():
    provider = profiled_provider(provider='test')
    record = [{'time': FIXED_TIME, 'carbon_intensity': FIXED_VALUE, 'provider': 'test_de'}]
    with patch('requests.get', return_value=make_response(record)) as mock_get:
        df = provider._read_metrics()
    params = mock_get.call_args[1]['params']
    assert params['provider'] == 'test_de'
    assert not df.empty


def test_read_metrics_with_simulation_uuid():
    sim_id = uuid.uuid4()
    provider = profiled_provider(simulation_uuid=sim_id)
    with patch('requests.get', return_value=make_response(HISTORY_RECORD)) as mock_get:
        provider._read_metrics()
    params = mock_get.call_args[1]['params']
    assert params['simulation_id'] == str(sim_id)


# --- _read_metrics: fallback path ---

def _make_get_with_fallback(fallback_json):
    def side_effect(url, **_kwargs):
        if 'history' in url:
            return make_response([])
        return make_response(fallback_json)
    return side_effect


def test_empty_history_triggers_primary_fallback():
    provider = profiled_provider()
    fallback = [{'time': FIXED_TIME, 'carbon_intensity': 99, 'provider': FIXED_PROVIDER}]
    with patch('requests.get', side_effect=_make_get_with_fallback(fallback)) as mock_get:
        df = provider._read_metrics()
    urls_called = [c[0][0] for c in mock_get.call_args_list]
    assert any('current/primary' in u for u in urls_called)
    assert df['value'].iloc[0] == 99


def test_empty_history_with_provider_filter_uses_current_endpoint():
    provider = profiled_provider(provider='test')
    fallback = [
        {'time': FIXED_TIME, 'carbon_intensity': 77, 'provider': 'test_de'},
        {'time': FIXED_TIME, 'carbon_intensity': 55, 'provider': 'other_de'},
    ]
    with patch('requests.get', side_effect=_make_get_with_fallback(fallback)) as mock_get:
        df = provider._read_metrics()
    urls_called = [c[0][0] for c in mock_get.call_args_list]
    assert any(u.endswith('/carbon-intensity/current') for u in urls_called)
    assert all(row['provider'] == 'test_de' for _, row in df.iterrows())


# --- _read_metrics: error paths ---

def test_http_error_returns_none_and_logs():
    provider = profiled_provider()
    with patch('requests.get', return_value=make_response(status_code=500)):
        result = provider._read_metrics()
    assert result is None
    assert '500' in provider.error_string


def test_network_failure_returns_none_and_logs():
    provider = profiled_provider()
    with patch('requests.get', side_effect=requests.RequestException('timeout')):
        result = provider._read_metrics()
    assert result is None
    assert provider.error_string != ''


def test_fallback_http_error_returns_none():
    provider = profiled_provider()

    def side_effect(url, **_kwargs):
        if 'history' in url:
            return make_response([])
        return make_response(status_code=503)

    with patch('requests.get', side_effect=side_effect):
        result = provider._read_metrics()
    assert result is None


def test_fallback_network_failure_returns_none():
    provider = profiled_provider()

    def side_effect(url, **_kwargs):
        if 'history' in url:
            return make_response([])
        raise requests.RequestException('unreachable')

    with patch('requests.get', side_effect=side_effect):
        result = provider._read_metrics()
    assert result is None


# --- _read_metrics: missing start/end times ---

def test_read_metrics_without_profiling_raises():
    provider = make_provider()
    with pytest.raises(RuntimeError, match='start_profiling'):
        provider._read_metrics()


# --- multiple records ---

def test_multiple_records_sorted_by_time():
    provider = profiled_provider()
    records = [
        {'time': '2026-04-28T12:10:00Z', 'carbon_intensity': 80, 'provider': FIXED_PROVIDER},
        {'time': '2026-04-28T12:00:00Z', 'carbon_intensity': 40, 'provider': FIXED_PROVIDER},
    ]
    with patch('requests.get', return_value=make_response(records)):
        df = provider._read_metrics()
    assert df['time'].is_monotonic_increasing
    assert df['value'].iloc[0] == 40
    assert df['value'].iloc[1] == 80
