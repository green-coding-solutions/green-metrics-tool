import shutil
import pytest
import requests
import uuid
import tempfile
import yaml
from datetime import datetime, timedelta, timezone


from pathlib import Path
from unittest.mock import patch, MagicMock

from lib.db import DB
from lib.global_config import GlobalConfig
from lib.scenario_runner import ScenarioRunner
from metric_providers.carbon.intensity.elephant.machine.provider import CarbonIntensityElephantMachineProvider
from metric_providers.base import MetricProviderConfigurationError

TESTS_DIR = Path(__file__).resolve().parent.parent
GMT_ROOT_DIR = TESTS_DIR.parent

GMT_METRICS_DIR = Path(tempfile.mkdtemp(prefix='green-metrics-tool-metrics-'))

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
    defaults = {'region': 'DE', 'provider': 'test', 'elephant': ELEPHANT_CONFIG, 'folder': GMT_METRICS_DIR, 'skip_check': True}
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
        CarbonIntensityElephantMachineProvider(region='DE', provider='test', elephant=None, folder=GMT_METRICS_DIR, skip_check=True)


def test_incomplete_elephant_config_raises():
    with pytest.raises(MetricProviderConfigurationError):
        CarbonIntensityElephantMachineProvider(region='DE', provider='test', elephant={'host': 'localhost'}, folder=GMT_METRICS_DIR, skip_check=True)


def test_missing_provider_without_simulation_raises():
    with pytest.raises(MetricProviderConfigurationError, match='provider'):
        CarbonIntensityElephantMachineProvider(region='DE', elephant=ELEPHANT_CONFIG, folder=GMT_METRICS_DIR, skip_check=True)


# --- check_system ---

def test_check_system_success():
    provider = make_provider()
    current_data = [{'time': FIXED_TIME, 'carbon_intensity': FIXED_VALUE, 'provider': 'test_de'}]

    def side_effect(url, **_):
        if '/health' in url:
            return make_response({'status': 'healthy'})
        return make_response(current_data)

    with patch('requests.get', side_effect=side_effect) as mock_get:
        provider.check_system()

    assert mock_get.call_args_list[0][0][0] == f'{BASE_URL}/health'


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
    assert 'update' not in call_kwargs[1]['params']


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
    assert params['simulationId'] == str(sim_id)


# --- _read_metrics: fallback path ---

def _make_get_with_fallback(fallback_json):
    def side_effect(url, **_kwargs):
        if 'history' in url:
            return make_response([])
        return make_response(fallback_json)
    return side_effect


def test_empty_history_triggers_primary_fallback():
    provider = profiled_provider(provider=None, simulation_uuid=uuid.uuid4())
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


def test_empty_history_with_simulation_uses_simulation_fallback():
    sim_id = uuid.uuid4()
    provider = profiled_provider(provider=None, simulation_uuid=sim_id)
    fallback = {'simulationId': str(sim_id), 'carbon_intensity': 66}

    with patch('requests.get', side_effect=_make_get_with_fallback(fallback)) as mock_get:
        df = provider._read_metrics()

    fallback_call = mock_get.call_args_list[1]
    assert fallback_call[1]['params']['simulationId'] == str(sim_id)
    assert df['value'].iloc[0] == 66
    assert df['provider'].iloc[0] == str(sim_id)


# --- _read_metrics: error paths ---

def test_http_error_returns_none_and_logs():
    provider = profiled_provider()
    with patch('requests.get', return_value=make_response(status_code=500)):
        with pytest.raises(RuntimeError, match='500'):
            provider._read_metrics()


def test_network_failure_returns_none_and_logs():
    provider = profiled_provider()
    with patch('requests.get', side_effect=requests.RequestException('timeout')):
        with pytest.raises(RuntimeError, match='timeout'):
            provider._read_metrics()


def test_fallback_http_error_returns_none():
    provider = profiled_provider()

    def side_effect(url, **_):
        if 'history' in url:
            return make_response([])
        return make_response(status_code=503)

    with patch('requests.get', side_effect=side_effect):
        with pytest.raises(RuntimeError, match='503'):
            provider._read_metrics()


def test_fallback_network_failure_returns_none():
    provider = profiled_provider()

    def side_effect(url, **_):
        if 'history' in url:
            return make_response([])
        raise requests.RequestException('unreachable')

    with patch('requests.get', side_effect=side_effect):
        with pytest.raises(RuntimeError, match='unreachable'):
            provider._read_metrics()


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


# --- sampling_rate expansion ---

def test_read_metrics_expands_to_sampling_rate():
    # Regression test: expand_to_sampling_rate accesses _start_time/_end_time via
    # a module-level function; previously used double-underscore names which caused
    # AttributeError when sampling_rate > 0 due to Python's name-mangling rules.
    provider = make_provider(sampling_rate=1000)  # 1 s in ms
    provider._start_time = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
    provider._end_time   = datetime(2026, 4, 28, 12, 0, 3, tzinfo=timezone.utc)

    records = [{'time': '2026-04-28T12:00:00Z', 'carbon_intensity': 42, 'provider': FIXED_PROVIDER}]
    with patch('requests.get', return_value=make_response(records)):
        df = provider._read_metrics()

    # 3-second window at 1 s steps → 4 rows (0 s, 1 s, 2 s, 3 s)
    assert len(df) == 4
    assert (df['value'] == 42).all()
    assert df['time'].is_monotonic_increasing


# --- Live integration test (hits the real Elephant service) ---

LIVE_ELEPHANT_CONFIG = {'host': 'elephant.green-coding.io', 'port': 443, 'protocol': 'https'}
LIVE_ELEPHANT_BASE_URL = 'https://elephant.green-coding.io'


def _live_elephant_reachable():
    try:
        requests.get(f"{LIVE_ELEPHANT_BASE_URL}/health", timeout=5).close()
        return True
    except requests.RequestException:
        return False


@pytest.mark.skipif(not _live_elephant_reachable(), reason='Elephant service not reachable')
def test_live_check_system_passes():
    provider = CarbonIntensityElephantMachineProvider(
        region='DE', provider='bundesnetzagentur', elephant=LIVE_ELEPHANT_CONFIG, folder=GMT_METRICS_DIR, skip_check=True,
    )
    provider.check_system()


@pytest.mark.skipif(not _live_elephant_reachable(), reason='Elephant service not reachable')
def test_live_read_metrics_returns_real_data():
    provider = CarbonIntensityElephantMachineProvider(
        region='DE', provider='bundesnetzagentur', elephant=LIVE_ELEPHANT_CONFIG, folder=GMT_METRICS_DIR, skip_check=True,
    )
    provider.start_profiling()
    # Widen the window so the history endpoint has data even on a fast run
    provider._start_time = datetime.now(timezone.utc) - timedelta(hours=2)
    provider.stop_profiling()
    provider._end_time = datetime.now(timezone.utc)

    df = provider._read_metrics()

    assert not df.empty, f"Expected data from live Elephant service. stderr: {provider.get_stderr()}"
    assert (df['value'] > 0).all()


@pytest.mark.skipif(not _live_elephant_reachable(), reason='Elephant service not reachable')
def test_live_full_gmt_run_creates_metric_and_phase_stat():
    # End-to-end integration test: run a real GMT scenario with the
    # elephant carbon intensity provider configured against the live service
    # and check that values land in the measurement_metrics, measurement_values
    # and phase_stats tables.

    base_config_path = TESTS_DIR / 'test-config.yml'

    with open(base_config_path, encoding='utf-8') as fh:
        config = yaml.safe_load(fh)

    common = config['measurement']['metric_providers'].setdefault('common', {}) or {}
    # sampling_rate must be set so helpers.expand_to_sampling_rate fans the few
    # API records into a dense series across the measurement window; otherwise
    # the phase_stats time-window filter would drop them and
    # reconstruct_runtime_phase would produce no row for carbon_intensity_*.
    common['carbon_intensity_elephant_machine'] = {
        'region': 'DE',
        'provider': 'bundesnetzagentur',
        'elephant': LIVE_ELEPHANT_CONFIG,
        'sampling_rate': 99,
    }
    config['measurement']['metric_providers']['common'] = common

    tmp_config_dir = Path(tempfile.mkdtemp(prefix='gmt-elephant-config-'))
    tmp_config = tmp_config_dir / 'test-config.yml'
    with open(tmp_config, 'w', encoding='utf-8') as fh:
        yaml.safe_dump(config, fh)

    GlobalConfig().override_config(config_location=tmp_config.as_posix())

    try:
        runner = ScenarioRunner(
            uri=GMT_ROOT_DIR.as_posix(),
            uri_type='folder',
            filename='tests/data/usage_scenarios/basic_stress.yml',
            dev_no_system_checks=True,
            dev_cache_build=True,
            dev_no_sleeps=True,
            dev_no_metrics=False,
            dev_no_phase_stats=False,
            dev_no_container_dependency_collection=True,
            skip_download_dependencies=True,
            skip_optimizations=True,
        )
        run_id = runner.run()

        db_metric_name = 'carbon_intensity_elephant_machine'
        # provider_filter.lower() + '_' + region.lower(); see provider.py:108
        expected_detail_name = 'bundesnetzagentur_de'

        # --- measurement_metrics: the metric was registered for the run ---
        metric_row = DB().fetch_one(
            'SELECT id, metric, detail_name, unit FROM measurement_metrics '
            'WHERE run_id = %s AND metric = %s',
            params=(run_id, db_metric_name),
            fetch_mode='dict',
        )
        assert metric_row is not None, f'No measurement_metrics row for {db_metric_name}'
        assert metric_row['detail_name'] == expected_detail_name
        assert metric_row['unit'] == 'gCO2e/kWh'

        # --- measurement_values: at least one raw datapoint was stored ---
        values = DB().fetch_all(
            'SELECT value FROM measurement_values WHERE measurement_metric_id = %s',
            params=(metric_row['id'],),
            fetch_mode='dict',
        )
        assert len(values) >= 1, 'No measurement_values rows stored for the live carbon intensity'
        assert all(row['value'] > 0 for row in values), 'Carbon intensity values must be positive'

        # --- phase_stats: aggregated MEAN row was computed for the [RUNTIME] phase ---
        phase_stat = DB().fetch_one(
            "SELECT value, type, unit, max_value, min_value FROM phase_stats "
            "WHERE run_id = %s AND metric = %s AND phase LIKE %s",
            params=(run_id, db_metric_name, '%_[RUNTIME]'),
            fetch_mode='dict',
        )
        assert phase_stat is not None, f'No phase_stats row for {db_metric_name}'
        assert phase_stat['type'] == 'MEAN'
        assert phase_stat['unit'] == 'gCO2e/kWh'
        assert phase_stat['value'] > 0
        assert phase_stat['min_value'] <= phase_stat['value'] <= phase_stat['max_value']
        # Sanity bound for real-world DE grid carbon intensity
        assert phase_stat['max_value'] < 2000, (
            f"Carbon intensity max {phase_stat['max_value']} gCO2e/kWh implausibly high for live DE data"
        )
    finally:
        GlobalConfig().override_config(config_location=base_config_path.as_posix())
        shutil.rmtree(tmp_config_dir, ignore_errors=True)
