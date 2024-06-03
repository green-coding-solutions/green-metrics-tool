import os
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests
from runner import Runner


config = GlobalConfig(config_name='test-config.yml').config

#pylint: disable=unused-argument # unused arguement off for now - because there are no running tests in this file
@pytest.fixture(name="reset_config")
def reset_config_fixture():
    idle_start_time = config['measurement']['idle-time-start']
    idle_time_end = config['measurement']['idle-time-end']
    flow_process_runtime = config['measurement']['flow-process-runtime']
    yield
    config['measurement']['idle-time-start'] = idle_start_time
    config['measurement']['idle-time-end'] = idle_time_end
    config['measurement']['flow-process-runtime'] = flow_process_runtime

# Rethink how to do this test entirely
def wip_test_idle_start_time(reset_config):
    config['measurement']['idle-time-start'] = 2
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
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
    config['measurement']['idle-time-end'] = 2
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
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
    config['measurement']['flow-process-runtime'] = .1
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    with pytest.raises(RuntimeError) as err:
        runner.run()
    expected_exception = 'Process exceeded runtime of 0.1s: stress-ng -c 1 -t 1 -q'
    assert expected_exception in str(err.value), \
        Tests.assertion_info(expected_exception, str(err.value))
