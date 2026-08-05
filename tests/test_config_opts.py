import os
import pytest
import io
from contextlib import redirect_stdout, redirect_stderr
import subprocess
from psycopg.errors import RaiseException as psycopg_RaiseException

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')

from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests
from lib.scenario_runner import ScenarioRunner

QUICK_OPTIONS= {
    'dev_no_save': True,
    'dev_no_sleeps': True,
    'dev_cache_build': True,
    'dev_no_metrics': True,
    'dev_no_system_checks': True,
    'dev_cache_repos': True,
    'dev_no_phase_stats': True,
    'dev_no_container_dependency_collection': True,

    'skip_volume_inspect': False,
    'skip_download_dependencies': False,
    'skip_unsafe': False,
    'skip_optimizations': False,
}

def test_global_timeout():

    measurement_total_duration = 1

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', measurement_total_duration=1, measurement_pre_test_sleep=1, measurement_baseline_duration=1, measurement_idle_duration=1, measurement_post_test_sleep=1, measurement_wait_time_dependencies=1, **QUICK_OPTIONS)

    out = io.StringIO()
    err = io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            runner.run()
    except subprocess.TimeoutExpired as e:
        assert str(e).startswith("Command '['docker', 'run', '--rm', ") and f"timed out after {measurement_total_duration} seconds" in str(e)
        return
    except TimeoutError as e:
        assert str(e) == f"Timeout of {measurement_total_duration} s was exceeded. This can be configured in the user authentication for 'total_duration'."
        return

    assert False, \
        Tests.assertion_info('Timeout was not raised', str(out.getvalue()))


def test_invalid_combination_measurement_flow_process_duration():

    with pytest.raises(ValueError) as err:
        ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', measurement_total_duration=10, measurement_flow_process_duration=20, **QUICK_OPTIONS)

    assert str(err.value) == 'Cannot run flows due to configuration error. Measurement_total_duration must be >= measurement_flow_process_duration, otherwise the flow will run into a timeout in every case. Values are: measurement_flow_process_duration: 20 and measurement_total_duration: 10'

def test_provider_disabling_not_active_by_default():
    out = io.StringIO()
    err = io.StringIO()

    filtered_options = {k: v for k, v in QUICK_OPTIONS.items() if k != 'dev_no_metrics'}
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/stress-application/usage_scenario.yml',  **filtered_options)

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('import_metric_providers')

    assert 'Not importing' not in out.getvalue()

def test_provider_disabling_working():
    out = io.StringIO()
    err = io.StringIO()

    GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/test-config-extra-network-and-duplicate-psu-providers.yml")

    filtered_options = {k: v for k, v in QUICK_OPTIONS.items() if k not in ('dev_no_save', 'dev_no_metrics') }
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/stress-application/usage_scenario.yml', disabled_metric_providers=['network_connections_proxy_container'], **filtered_options)

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('initialize_run')

    assert 'Not importing network_connections_proxy_container as disabled per user settings' in out.getvalue()

    run_data = DB().fetch_one('SELECT measurement_config FROM runs WHERE id = %s', (runner._run_id,))[0]

    providers = list(run_data['configured_metric_providers'].keys())
    # or check bc in linux / macos there is a different result set of configured providers
    assert providers == ['psu_energy_ac_sdia_machine', 'cpu_utilization_mach_system', 'psu_energy_ac_xgboost_machine', 'carbon_intensity_static_machine'] or providers == ['disk_used_statvfs_system', 'network_io_procfs_system', 'memory_used_procfs_system', 'psu_energy_ac_sdia_machine', 'cpu_utilization_procfs_system', 'psu_energy_ac_xgboost_machine', 'carbon_intensity_static_machine'], 'Network Connections provider still in configured_metric_providers' #pylint: disable=consider-using-in

# Runs a full runner.run() with real metric providers (dev_no_metrics excluded from
# filtered_options below) - must never overlap with another test that also starts real metric
# providers. See the comment on pytestmark in tests/smoke_test.py for why xdist_group is what
# actually prevents that under -n.
@pytest.mark.xdist_group(name="real-metric-providers")
def test_phase_padding():
    out = io.StringIO()
    err = io.StringIO()

    EXPECTED_PHASE_NUMBER = 5

    filtered_options = {k: v for k, v in QUICK_OPTIONS.items() if k not in ('dev_no_save', 'dev_no_metrics', 'dev_no_phase_stats') }
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/noop.yml', **filtered_options)

    with redirect_stdout(out), redirect_stderr(err):
        run_id = runner.run()

    assert '>>>> MEASUREMENT SUCCESSFULLY COMPLETED <<<<' in out.getvalue()

    query = 'SELECT phases from runs WHERE id = %s '
    phases = DB().fetch_one(query, (run_id,), fetch_mode='dict')

    assert phases['phases'][EXPECTED_PHASE_NUMBER]['name'] == 'Testing Noop'
    phase = phases['phases'][EXPECTED_PHASE_NUMBER]

    query = """
            SELECT mv.value from measurement_metrics as mm
            LEFT JOIN measurement_values mv on mv.measurement_metric_id = mm.id
            WHERE
                mm.run_id = %s
                AND mm.metric = 'psu_energy_ac_xgboost_machine'
                AND mm.detail_name = '[MACHINE]'
                AND mv.time > %s
                AND mv.time < %s
            ORDER BY mv.time ASC
            """

    metrics = DB().fetch_all(query, (run_id, phase['start'], phase['end']))

    query = """
            SELECT mv.value from measurement_metrics as mm
            LEFT JOIN measurement_values mv on mv.measurement_metric_id = mm.id
            WHERE
                mm.run_id = %s
                AND mm.metric = 'psu_energy_ac_xgboost_machine'
                AND mm.detail_name = '[MACHINE]'
                AND mv.time >= %s
            ORDER BY mv.time ASC
            LIMIT 1
            """

    value_next_tick = DB().fetch_one(query, (run_id, phase['end']))[0]

    metrics_sum_no_padding = 0
    for el in metrics:
        metrics_sum_no_padding += el[0]

    query = """
            SELECT value FROM phase_stats
            WHERE run_id = %s
            AND metric = 'psu_energy_ac_xgboost_machine'
            AND detail_name = '[MACHINE]'
            AND phase = %s
            """

    phase_stats = DB().fetch_all(query, (run_id, f"00{EXPECTED_PHASE_NUMBER}_{phase['name']}"))
    assert len(phase_stats) == 1

    assert phase_stats[0][0] == metrics_sum_no_padding + value_next_tick


def test_invalid_category():

    filtered_options = {k: v for k, v in QUICK_OPTIONS.items() if k not in ('dev_no_save', ) }
    with pytest.raises(psycopg_RaiseException) as err:
        runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', category_ids=[3000], **filtered_options)
        runner.run()

    assert str(err.value) == 'At least one category ID supplied ({3000}) does not exist as category. Please check if category is a typo otherwise add category first\nCONTEXT:  PL/pgSQL function validate_category_ids() line 12 at RAISE'
