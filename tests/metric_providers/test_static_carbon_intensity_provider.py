import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas
import pytest
import yaml

from lib.db import DB
from lib.global_config import GlobalConfig
from lib.scenario_runner import ScenarioRunner
from metric_providers.base import MetricProviderConfigurationError
from metric_providers.carbon.intensity.static.machine.provider import (
    CarbonIntensityStaticMachineProvider,
)

TESTS_DIR = Path(__file__).resolve().parent.parent
GMT_ROOT_DIR = TESTS_DIR.parent

GMT_METRICS_DIR = Path(tempfile.mkdtemp(prefix='green-metrics-tool-metrics-static-'))


@pytest.fixture(autouse=True, scope='module')
def setup_metrics_dir():
    GMT_METRICS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    shutil.rmtree(GMT_METRICS_DIR)


def make_provider(**kwargs):
    defaults = {'value': 334, 'folder': GMT_METRICS_DIR, 'skip_check': True}
    defaults.update(kwargs)
    return CarbonIntensityStaticMachineProvider(**defaults)


def profiled_provider(**kwargs):
    provider = make_provider(**kwargs)
    provider.start_profiling()
    provider.stop_profiling()
    return provider


# --- Constructor / config validation ---

def test_missing_value_raises():
    with pytest.raises(MetricProviderConfigurationError, match='value'):
        CarbonIntensityStaticMachineProvider(value=None, folder=GMT_METRICS_DIR, skip_check=True)


def test_non_numeric_value_raises():
    with pytest.raises(MetricProviderConfigurationError, match='numeric'):
        CarbonIntensityStaticMachineProvider(value='not-a-number', folder=GMT_METRICS_DIR, skip_check=True)


def test_numeric_string_value_accepted():
    provider = CarbonIntensityStaticMachineProvider(value='250', folder=GMT_METRICS_DIR, skip_check=True)
    assert provider.value == 250.0


def test_float_value_accepted():
    provider = make_provider(value=333.7)
    assert provider.value == 333.7


# --- check_system ---

def test_check_system_is_noop():
    provider = make_provider()
    # Should not require any external resource or raise
    assert provider.check_system() is True


# --- profiling lifecycle ---

def test_has_started_toggles():
    provider = make_provider()
    assert provider.has_started() is False
    provider.start_profiling()
    assert provider.has_started() is True
    provider.stop_profiling()
    assert provider.has_started() is False


def test_read_metrics_without_profiling_raises():
    provider = make_provider()
    with pytest.raises(RuntimeError, match='start_profiling'):
        provider._read_metrics()


# --- _read_metrics ---

def test_read_metrics_returns_configured_value():
    provider = profiled_provider(value=412)
    df = provider._read_metrics()
    assert not df.empty
    assert (df['value'] == 412).all()


def test_read_metrics_rounds_float_value():
    provider = profiled_provider(value=333.7)
    df = provider._read_metrics()
    assert (df['value'] == 334).all()


def test_read_metrics_provider_column_is_static():
    provider = profiled_provider()
    df = provider._read_metrics()
    assert (df['provider'] == 'static').all()


def test_read_metrics_without_sampling_rate_emits_endpoints():
    provider = profiled_provider()  # default sampling_rate=-1
    df = provider._read_metrics()
    assert len(df) == 2
    assert df['time'].is_monotonic_increasing


def test_read_metrics_value_is_integer_dtype():
    provider = profiled_provider()
    df = provider._read_metrics()
    assert df['value'].dtype == 'int64'


def test_read_metrics_handles_zero_duration():
    # Same start/end timestamps would otherwise produce duplicate times; provider must guard against it
    provider = make_provider()
    now = datetime.now(timezone.utc)
    provider._start_time = now
    provider._end_time = now
    provider._has_started = False
    df = provider._read_metrics()
    assert len(df) == 2
    assert df['time'].iloc[1] > df['time'].iloc[0]


# --- sampling_rate expansion ---

def test_read_metrics_expands_to_sampling_rate():
    provider = make_provider(sampling_rate=1000)  # 1 s in ms
    provider._start_time = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
    provider._end_time = datetime(2026, 4, 28, 12, 0, 3, tzinfo=timezone.utc)

    df = provider._read_metrics()

    # 3-second window at 1 s steps → 4 rows (0 s, 1 s, 2 s, 3 s)
    assert len(df) == 4
    assert (df['value'] == 334).all()
    assert df['time'].is_monotonic_increasing


# --- public read_metrics end-to-end shape ---

def test_public_read_metrics_returns_expected_columns():
    provider = make_provider(sampling_rate=500)
    provider._start_time = datetime(2026, 4, 28, 12, 0, 0, tzinfo=timezone.utc)
    provider._end_time = datetime(2026, 4, 28, 12, 0, 2, tzinfo=timezone.utc)

    df = provider.read_metrics()

    assert isinstance(df, pandas.DataFrame)
    assert {'time', 'value', 'detail_name', 'metric', 'unit'}.issubset(df.columns)
    assert (df['metric'] == 'carbon_intensity_static_machine').all()
    assert (df['unit'] == 'gCO2e/kWh').all()
    assert (df['detail_name'] == 'static').all()


# --- Integration: full GMT run with the static provider ---

# Merges into the base test-config.yml 'common' providers rather than replacing it, so this starts
# the full default set of real metric providers for real (dev_no_system_checks=True disables the
# check for this test only) - must never overlap with another test that also starts real metric
# providers. See the comment on pytestmark in tests/smoke_test.py for why xdist_group is what
# actually prevents that under -n.
@pytest.mark.xdist_group(name="real-metric-providers")
def test_full_gmt_run_creates_metric_and_phase_stat():
    static_value = 444

    base_config_path = TESTS_DIR / 'test-config.yml'

    with open(base_config_path, encoding='utf-8') as fh:
        config = yaml.safe_load(fh)

    common = config['measurement']['metric_providers'].setdefault('common', {}) or {}
    common['carbon_intensity_static_machine'] = {
        'value': static_value,
        'sampling_rate': 99,
    }
    config['measurement']['metric_providers']['common'] = common

    tmp_config_dir = Path(tempfile.mkdtemp(prefix='gmt-static-carbon-config-'))
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

        db_metric_name = 'carbon_intensity_static_machine'

        # --- measurement_metrics: the metric was registered for the run ---
        metric_row = DB().fetch_one(
            'SELECT id, metric, detail_name, unit FROM measurement_metrics '
            'WHERE run_id = %s AND metric = %s',
            params=(run_id, db_metric_name),
            fetch_mode='dict',
        )
        assert metric_row is not None, f'No measurement_metrics row for {db_metric_name}'
        assert metric_row['detail_name'] == 'static'
        assert metric_row['unit'] == 'gCO2e/kWh'

        # --- measurement_values: stored datapoints all carry the configured value ---
        values = DB().fetch_all(
            'SELECT value FROM measurement_values WHERE measurement_metric_id = %s',
            params=(metric_row['id'],),
            fetch_mode='dict',
        )
        assert len(values) >= 1, 'No measurement_values rows stored for the static carbon intensity'
        assert all(row['value'] == static_value for row in values)

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
        assert phase_stat['value'] == static_value
        assert phase_stat['min_value'] == static_value
        assert phase_stat['max_value'] == static_value
    finally:
        GlobalConfig().override_config(config_location=base_config_path.as_posix())
        shutil.rmtree(tmp_config_dir, ignore_errors=True)
