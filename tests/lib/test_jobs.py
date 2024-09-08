import os
import subprocess
from unittest.mock import patch
import pytest
import psycopg

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib import utils
from lib.global_config import GlobalConfig
from tools.machine import Machine
from lib.job.base import Job
from tests import test_functions as Tests

GlobalConfig().override_config(config_name='test-config.yml')
config = GlobalConfig().config

@pytest.fixture(autouse=True, name="register_machine")
def register_machine_fixture():
    machine = Machine(machine_id=1, description='test-machine')
    machine.register()


# This should be done once per module
@pytest.fixture(autouse=True, scope="module", name="build_image")
def build_image_fixture():
    subprocess.run(['docker', 'compose', '-f', f"{CURRENT_DIR}/../data/stress-application/compose.yml", 'build'], check=True)

def get_job(job_id):
    query = """
            SELECT
                *
            FROM
                jobs
            WHERE id = %s
            """
    data = DB().fetch_one(query, (job_id, ), fetch_mode='dict')
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
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-berlin/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'main'
    machine_id = 1

    job_id = Job.insert('run', name=name, url=url, email=None, branch=branch, filename=filename, machine_id=machine_id)
    assert job_id is not None
    job = Job.get_job('run')
    assert job._state == 'WAITING'

def test_simple_run_job():
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-berlin/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'main'
    machine_id = 1

    Job.insert('run', name=name, url=url, email=None, branch=branch, filename=filename, machine_id=machine_id)

    ps = subprocess.run(
            ['python3', '../tools/jobs.py', 'run', '--config-override', 'test-config.yml'],
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

def test_simple_cluster_run():
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-berlin/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'main'
    machine_id = 1

    Job.insert('run', name=name, url=url, email=None, branch=branch, filename=filename, machine_id=machine_id)

    ps = subprocess.run(
            ['python3', '../tools/client.py', '--testing', '--config-override', 'test-config.yml'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
    assert ps.stderr == '', Tests.assertion_info('No Error', ps.stderr)
    assert 'Successfully ended testing run of client.py' in ps.stdout,\
        Tests.assertion_info('Successfully ended testing run of client.py', ps.stdout)

    assert 'MEASUREMENT SUCCESSFULLY COMPLETED' in ps.stdout,\
        Tests.assertion_info('MEASUREMENT SUCCESSFULLY COMPLETED', ps.stdout)

def test_simple_run_job_missing_filename_branch():
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-berlin/pytest-dummy-repo'
    machine_id = 1

    with pytest.raises(RuntimeError):
        Job.insert('run', name=name, url=url, email=None, machine_id=machine_id)


def test_simple_run_job_wrong_machine_id():
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-berlin/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'main'
    machine_id = 100

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        Job.insert('run', name=name, url=url, email=None, branch=branch, filename=filename, machine_id=machine_id)


#pylint: disable=unused-variable # for the time being, until I get the mocking to work
## This test doesn't really make sense anymore as is, since we don't have "email jobs" in the same way,
## more that we send an email after a run job is finished.
def todo_test_simple_email_job():
    subject = utils.randomword(12)
    email = 'fakeemailaddress'
    message = 'simple job'

    Job.insert(
        'email',
        email=email,
        name=subject,
        message=message,
    )

    # Why is this patch not working :-(
    with patch('email_helpers.send_email') as send_email:
        ps = subprocess.run(
                ['python3', '../tools/jobs.py', 'email', '--config-override', 'test-config.yml'],
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding='UTF-8'
            )
        #send_email.assert_called_with(email, pid)
    assert ps.stderr == '', Tests.assertion_info('No Error', ps.stderr)
    job_success_message = 'Successfully processed jobs queue item.'
    assert job_success_message in ps.stdout,\
       Tests.assertion_info('Successfully processed jobs queue item.', ps.stdout)
