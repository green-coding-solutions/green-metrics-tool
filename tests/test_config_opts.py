import os
import pytest
import io
from contextlib import redirect_stdout, redirect_stderr
import subprocess

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')

from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests
from runner import Runner


GlobalConfig().override_config(config_name='test-config.yml')

def test_global_timeout():

    total_duration_new = 1
    total_duration_before = GlobalConfig().config['measurement']['total-duration']
    GlobalConfig().config['measurement']['total-duration'] = total_duration_new

    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_build=False, dev_no_sleeps=True, dev_no_metrics=True)

    out = io.StringIO()
    err = io.StringIO()
    try:
        with redirect_stdout(out), redirect_stderr(err):
            runner.run()
    except subprocess.TimeoutExpired as e:
        assert str(e).startswith("Command '['docker', 'run', '--rm', '-v',") and f"timed out after {total_duration_new} seconds" in str(e), \
        Tests.assertion_info(f"Command '['docker', 'run', '--rm', '-v', ... timed out after {total_duration_new} seconds", str(e))
        return
    except TimeoutError as e:
        assert str(e) == f"Timeout of {total_duration_new} s was exceeded. This can be configured in 'total-duration'.", \
        Tests.assertion_info(f"Timeout of {total_duration_new} s was exceeded. This can be configured in 'total-duration'.", str(e))
        return
    finally:
        GlobalConfig().config['measurement']['total-duration'] = total_duration_before # reset

    assert False, \
        Tests.assertion_info('Timeout was not raised', str(out.getvalue()))


#pylint: disable=unused-argument # unused arguement off for now - because there are no running tests in this file
@pytest.fixture(name="reset_config")
def reset_config_fixture():
    config = GlobalConfig().config
    idle_start_time = config['measurement']['idle-time-start']
    idle_time_end = config['measurement']['idle-time-end']
    flow_process_runtime = config['measurement']['flow-process-runtime']
    yield
    config['measurement']['idle-time-start'] = idle_start_time
    config['measurement']['idle-time-end'] = idle_time_end
    config['measurement']['flow-process-runtime'] = flow_process_runtime

# Rethink how to do this test entirely
def wip_test_idle_start_time(reset_config):
    GlobalConfig().config['measurement']['idle-time-start'] = 2
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    run_id = runner.run()
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

    timestamp_preidle = [note for note in notes if "Booting" in note[1]][0][0]
    timestamp_start = [note for note in notes if note[1] == 'Start of measurement'][0][0]

    #assert that the difference between the two timestamps is roughly 2 seconds
    diff = (timestamp_start - timestamp_preidle)/1000000
    assert 1.9 <= diff <= 2.1, \
        Tests.assertion_info('2s apart', f"timestamp difference of notes: {diff}s")

# Rethink how to do this test entirely
def wip_test_idle_end_time(reset_config):
    GlobalConfig().config['measurement']['idle-time-end'] = 2
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    run_id = runner.run()
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
    timestamp_postidle = [note for note in notes if note[1] == 'End of post-measurement idle'][0][0]
    timestamp_end = [note for note in notes if note[1] == 'End of measurement'][0][0]

    #assert that the difference between the two timestamps is roughly 2 seconds
    diff = (timestamp_postidle - timestamp_end)/1000000
    assert 1.9 <= diff <= 2.1, \
        Tests.assertion_info('2s apart', f"timestamp difference of notes: {diff}s")

def wip_test_process_runtime_exceeded(reset_config):
    GlobalConfig().config['measurement']['flow-process-runtime'] = .1
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    with pytest.raises(RuntimeError) as err:
        runner.run()
    expected_exception = 'Process exceeded runtime of 0.1s: stress-ng -c 1 -t 1 -q'
    assert expected_exception in str(err.value), \
        Tests.assertion_info(expected_exception, str(err.value))
