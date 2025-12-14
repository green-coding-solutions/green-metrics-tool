import os
import pytest
import io
from contextlib import redirect_stdout, redirect_stderr
import subprocess

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')

from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests
from lib.scenario_runner import ScenarioRunner

def test_global_timeout():

    measurement_total_duration = 1

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_cache_build=False, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True, measurement_total_duration=1, measurement_pre_test_sleep=1, measurement_baseline_duration=1, measurement_idle_duration=1, measurement_post_test_sleep=1, measurement_wait_time_dependencies=1)

    out = io.StringIO()
    err = io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            runner.run()
    except subprocess.TimeoutExpired as e:
        assert str(e).startswith("Command '['docker', 'run', '--rm', '-v',") and f"timed out after {measurement_total_duration} seconds" in str(e), \
        Tests.assertion_info(f"Command '['docker', 'run', '--rm', '-v', ... timed out after {measurement_total_duration} seconds", str(e))
        return
    except TimeoutError as e:
        assert str(e) == f"Timeout of {measurement_total_duration} s was exceeded. This can be configured in the user authentication for 'total_duration'.", \
        Tests.assertion_info(f"Timeout of {measurement_total_duration} s was exceeded. This can be configured in the user authentication for 'total_duration'.", str(e))
        return

    assert False, \
        Tests.assertion_info('Timeout was not raised', str(out.getvalue()))


def test_invalid_combination_measurement_flow_process_duration():

    with pytest.raises(ValueError) as err:
        ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_cache_build=False, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True, measurement_total_duration=10, measurement_flow_process_duration=20)

    assert str(err.value) == 'Cannot run flows due to configuration error. Measurement_total_duration must be >= measurement_flow_process_duration, otherwise the flow will run into a timeout in every case. Values are: measurement_flow_process_duration: 20 and measurement_total_duration: 10'

def test_provider_disabling_not_active_by_default():
    out = io.StringIO()
    err = io.StringIO()

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/stress-application/usage_scenario.yml', skip_unsafe=False, skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=False, dev_no_phase_stats=True)

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('import_metric_providers')

    assert 'Not importing' not in out.getvalue()

def test_provider_disabling_working():
    GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/test-config-extra-network-and-duplicate-psu-providers.yml")

    out = io.StringIO()
    err = io.StringIO()

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/stress-application/usage_scenario.yml', skip_unsafe=False, skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=False, dev_no_phase_stats=True, disabled_metric_providers=['NetworkConnectionsProxyContainerProvider'])

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('import_metric_providers')

    assert 'Not importing NetworkConnectionsProxyContainerProvider as disabled per user settings' in out.getvalue()


def test_phase_padding_inactive():
    out = io.StringIO()
    err = io.StringIO()

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/noop.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True, phase_padding=False)

    with redirect_stdout(out), redirect_stderr(err):
        run_id = runner.run()

    assert '>>>> MEASUREMENT SUCCESSFULLY COMPLETED <<<<' in out.getvalue()
    query = """
            SELECT
                time, note
            FROM
                notes
            WHERE
                run_id = %s
            ORDER BY
                time
            """

    notes = DB().fetch_all(query, (run_id,))

    # we count the array from the end as depending on if the test is executed alone or in conjunction with other tests 'alpine' will get pulled and produce a note at the beginning that extends the notes
    assert notes[-6][1] == 'Starting phase Testing Noop'
    assert notes[-5][1] == 'Ending phase Testing Noop [UNPADDED]'
    assert notes[-4][1] == 'Ending phase [RUNTIME] [UNPADDED]' # this implictely means we have no PADDED entries
    assert notes[-4][0] > notes[-5][0] - 300 # end times of reconstructed runtime and last sub-runtime are very close, but not exact, bc we only reconstruct phase_stats but not measurements table. 300 microseconds is a good cutoff

def test_phase_padding_active():
    out = io.StringIO()
    err = io.StringIO()

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/noop.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True, phase_padding=True)

    with redirect_stdout(out), redirect_stderr(err):
        run_id = runner.run()

    assert '>>>> MEASUREMENT SUCCESSFULLY COMPLETED <<<<' in out.getvalue()
    query = """
            SELECT
                time, note
            FROM
                notes
            WHERE
                run_id = %s
            ORDER BY
                time
            """

    notes = DB().fetch_all(query, (run_id,))

    # we count the array from the end as depending on if the test is executed alone or in conjunction with other tests 'alpine' will get pulled and produce a note at the beginning that extends the notes
    assert notes[-9][1] == 'Starting phase Testing Noop'
    assert notes[-8][1] == 'Ending phase Testing Noop [UNPADDED]'
    assert notes[-7][1] == 'Ending phase Testing Noop [PADDED]'
    FROM_MS_TO_US = 1000
    assert notes[-7][0] - notes[-8][0] == runner._phase_padding_ms*FROM_MS_TO_US

    assert notes[-6][1] == 'Ending phase [RUNTIME] [UNPADDED]'
