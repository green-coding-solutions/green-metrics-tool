#pylint: disable=redefined-outer-name, import-error, wrong-import-position, unused-argument

import os
import sys
import subprocess
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/..")
sys.path.append(f"{CURRENT_DIR}/../lib")

from db import DB
import utils
import test_functions as Tests
from global_config import GlobalConfig
from runner import Runner

PROJECT_NAME = 'test_' + utils.randomword(12)
config = GlobalConfig(config_name='test-config.yml').config

@pytest.fixture
def reset_config():
    idle_start_time = config['measurement']['idle-time-start']
    idle_time_end = config['measurement']['idle-time-end']
    flow_process_runtime = config['measurement']['flow-process-runtime']
    yield
    config['measurement']['idle-time-start'] = idle_start_time
    config['measurement']['idle-time-end'] = idle_time_end
    config['measurement']['flow-process-runtime'] = flow_process_runtime

@pytest.fixture(autouse=True, scope="module")
def build_image():
    uri = os.path.abspath(os.path.join(
            CURRENT_DIR, 'stress-application/'))
    subprocess.run(['docker', 'compose', '-f', uri+'/compose.yml', 'build'], check=True)

#pylint: disable=expression-not-assigned
def run_runner():
    uri = os.path.abspath(os.path.join(
            CURRENT_DIR, 'stress-application/'))
    pid = DB().fetch_one('INSERT INTO "projects" ("name","uri","email","last_run","created_at") \
                VALUES \
                (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(PROJECT_NAME, uri))[0]

    # Run the application
    runner = Runner(uri=uri, uri_type='folder', pid=pid, verbose_provider_boot=True, dev_repeat_run=True, skip_system_checks=True)
    runner.run()
    return pid

# Rethink how to do this test entirely
def wip_test_idle_start_time(reset_config):
    config['measurement']['idle-time-start'] = 2
    pid = run_runner()
    query = """
            SELECT
                time, note
            FROM
                notes
            WHERE
                project_id = %s
            ORDER BY
                time
            """

    notes = DB().fetch_all(query, (pid,))

    timestamp_preidle = [note for note in notes if "Booting" in note[1]][0][0]
    timestamp_start = [note for note in notes if note[1] == 'Start of measurement'][0][0]

    #assert that the difference between the two timestamps is roughly 2 seconds
    diff = (timestamp_start - timestamp_preidle)/1000000
    assert 1.9 <= diff <= 2.1, \
        Tests.assertion_info('2s apart', f"timestamp difference of notes: {diff}s")

# Rethink how to do this test entirely
def wip_test_idle_end_time(reset_config):
    config['measurement']['idle-time-end'] = 2
    pid = run_runner()
    query = """
            SELECT
                time, note
            FROM
                notes
            WHERE
                project_id = %s
            ORDER BY
                time
            """

    notes = DB().fetch_all(query, (pid,))
    timestamp_postidle = [note for note in notes if note[1] == 'End of post-measurement idle'][0][0]
    timestamp_end = [note for note in notes if note[1] == 'End of measurement'][0][0]

    #assert that the difference between the two timestamps is roughly 2 seconds
    diff = (timestamp_postidle - timestamp_end)/1000000
    assert 1.9 <= diff <= 2.1, \
        Tests.assertion_info('2s apart', f"timestamp difference of notes: {diff}s")

def wip_test_process_runtime_exceeded(reset_config):
    config['measurement']['flow-process-runtime'] = .1
    with pytest.raises(RuntimeError) as err:
        run_runner()
    expected_exception = 'Process exceeded runtime of 0.1s: stress-ng -c 1 -t 1 -q'
    assert expected_exception in str(err.value), \
        Tests.assertion_info(expected_exception, str(err.value))
