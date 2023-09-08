# test all functions in jobs.py
#pylint: disable=invalid-name,missing-docstring,too-many-statements,fixme

import os
import sys
import subprocess
from unittest.mock import patch
import pytest
import psycopg

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/../../tools")
sys.path.append(f"{CURRENT_DIR}/../../lib")

#pylint: disable=import-error,wrong-import-position
from db import DB
from jobs import Job
import test_functions as Tests
import utils
from global_config import GlobalConfig
GlobalConfig().override_config(config_name='test-config.yml')
config = GlobalConfig().config

@pytest.fixture(autouse=True, scope='module', name="cleanup_jobs")
def cleanup_jobs_fixture():
    yield
    DB().query('DELETE FROM jobs')

@pytest.fixture(autouse=True, scope='module', name="cleanup_runs")
def cleanup_runs_fixture():
    yield
    DB().query('DELETE FROM runs')

# This should be done once per module
@pytest.fixture(autouse=True, scope="module", name="build_image")
def build_image_fixture():
    subprocess.run(['docker', 'compose', '-f', f"{CURRENT_DIR}/../stress-application/compose.yml", 'build'], check=True)

def get_job(job_id):
    query = """
            SELECT
                *
            FROM
                jobs
            WHERE id = %s
            """
    data = DB().fetch_one(query, (job_id, ), row_factory=psycopg.rows.dict_row)
    if (data is None or data == []):
        return None

    return data

def test_no_run_job():
    ps = subprocess.run(
            ['python3', '../tools/jobs.py', 'run', '--config-override', 'test-config.yml'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
    print(ps.stderr)
    assert 'No job to process. Exiting' in ps.stdout,\
        Tests.assertion_info('No job to process. Exiting', ps.stdout)

def test_no_email_job():
    ps = subprocess.run(
            ['python3', '../tools/jobs.py', 'email', '--config-override', 'test-config.yml'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
    assert 'No job to process. Exiting' in ps.stdout,\
        Tests.assertion_info('No job to process. Exiting', ps.stdout)

def test_insert_job():
    job_id = Job.insert('Test Name', 'Test URL',  'Test Email', 'Test Branch', 'Test filename', 1)
    assert job_id is not None
    job = Job.get_job('run')
    assert job['state'] == 'WAITING'

def todo_test_simple_run_job():
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-berlin/pytest-dummy-repo'
    filename = 'usage_scenario.yml'

    Job.insert(name, url,  'Test Email', 'Test Branch', filename, 1)

    ps = subprocess.run(
            ['python3', '../tools/jobs.py', 'run', '--config-override', 'test-config.yml', '--skip-system-checks'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )

    assert ps.stderr == '', Tests.assertion_info('No Error', ps.stderr)
    assert 'Successfully processed jobs queue item.' in ps.stdout,\
        Tests.assertion_info('Successfully processed jobs queue item.', ps.stdout)
    assert 'MEASUREMENT SUCCESSFULLY COMPLETED' in ps.stdout,\
        Tests.assertion_info('MEASUREMENT SUCCESSFULLY COMPLETED', ps.stdout)

#pylint: disable=unused-variable # for the time being, until I get the mocking to work
def todo_test_simple_email_job():
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-berlin/pytest-dummy-repo'
    email = 'fakeemailaddress'
    filename = 'usage_scenario.yml'

    Job.insert(name, url, email, 'Test Branch', filename, 1)

    # Why is this patch not working :-(
    with patch('email_helpers.send_report_email') as send_email:
        ps = subprocess.run(
                ['python3', '../tools/jobs.py', 'email', '--config-override', 'test-config.yml'],
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding='UTF-8'
            )
        #send_email.assert_called_with(email, pid)
    assert ps.stderr == '', Tests.assertion_info('No Error', ps.stderr)
    assert ps.stdout == 'Successfully processed jobs queue item.\n',\
        Tests.assertion_info('Successfully processed jobs queue item.', ps.stdout)
