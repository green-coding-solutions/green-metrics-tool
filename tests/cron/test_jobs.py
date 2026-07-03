import os
import subprocess
from pathlib import Path
from unittest.mock import patch
import pytest
import psycopg

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
GMT_DIR = Path(CURRENT_DIR).parent.parent.as_posix()

from lib.db import DB
from lib import utils
from lib.job.base import Job
from lib.user import User
from tests import test_functions as Tests

# This should be done once per module
@pytest.fixture(autouse=True, scope="module", name="build_image")
def build_image_fixture():
    Tests.build_image_fixture()


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
            ['python3', '../cron/jobs.py', 'run', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/../test-config.yml"],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )

    assert 'No job to process. Exiting' in ps.stdout,\
        Tests.assertion_info('No job to process. Exiting', ps.stdout)

def test_no_email_job():
    ps = subprocess.run(
            ['python3', '../cron/jobs.py', 'email', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/../test-config.yml"],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
    assert 'No job to process. Exiting' in ps.stdout,\
        Tests.assertion_info('No job to process. Exiting', ps.stdout)

def test_insert_job():
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'main'
    machine_id = 1

    job_id = Job.insert('run', user_id=1, name=name, url=url, branch=branch, filename=filename, machine_id=machine_id)
    assert job_id is not None
    job = Job.get_job('run')
    assert job._state == 'WAITING'

def test_simple_run_job_no_quota():
    Tests.shorten_sleep_times(1)

    name = utils.randomword(12)
    url = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'main'
    machine_id = 1

    Job.insert('run', user_id=1, name=name, url=url, branch=branch, filename=filename, machine_id=machine_id)

    ps = subprocess.run(
            ['python3', '../cron/jobs.py', 'run', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/../test-config.yml"],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )

    assert ps.stderr == '', Tests.assertion_info('No Error', f"STDOUT:\n{ps.stdout}\nSTDERR:\n{ps.stderr}")
    assert 'Successfully processed jobs queue item.' in ps.stdout,\
        Tests.assertion_info('Successfully processed jobs queue item.', ps.stdout)
    assert 'MEASUREMENT SUCCESSFULLY COMPLETED' in ps.stdout,\
        Tests.assertion_info('MEASUREMENT SUCCESSFULLY COMPLETED', ps.stdout)

def test_simple_run_job_quota_gets_deducted():
    Tests.shorten_sleep_times(1)

    name = utils.randomword(12)
    url = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'main'
    machine_id = 1

    Job.insert('run', user_id=1, name=name, url=url, branch=branch, filename=filename, machine_id=machine_id)

    user = User(1)
    user._capabilities['measurement']['quotas'] = {'1': 10_000 * 60} # typical quota is 10.000 minutes
    user.update()

    ps = subprocess.run(
            ['python3', '../cron/jobs.py', 'run', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/../test-config.yml"],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )

    assert ps.stderr == '', Tests.assertion_info('No Error', f"STDOUT:\n{ps.stdout}\nSTDERR:\n{ps.stderr}")
    assert 'Successfully processed jobs queue item.' in ps.stdout,\
        Tests.assertion_info('Successfully processed jobs queue item.', ps.stdout)
    assert 'MEASUREMENT SUCCESSFULLY COMPLETED' in ps.stdout,\
        Tests.assertion_info('MEASUREMENT SUCCESSFULLY COMPLETED', ps.stdout)
    assert User(1)._capabilities['measurement']['quotas']['1'] < 10_000 * 60

def test_simple_run_job_with_variables():
    Tests.shorten_sleep_times(1)

    name = utils.randomword(12)
    url = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'usage_scenario_variables'
    machine_id = 1
    usage_scenario_variables = {'__GMT_VAR_COMMAND__': 'stress-ng'}

    Job.insert('run', user_id=1, name=name, url=url, branch=branch, filename=filename, machine_id=machine_id, usage_scenario_variables=usage_scenario_variables)

    ps = subprocess.run(
            ['python3', '../cron/jobs.py', 'run', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/../test-config.yml"],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )

    assert ps.stderr == '', Tests.assertion_info('No Error', f"STDOUT:\n{ps.stdout}\nSTDERR:\n{ps.stderr}")
    assert 'Successfully processed jobs queue item.' in ps.stdout,\
        Tests.assertion_info('Successfully processed jobs queue item.', ps.stdout)
    assert 'MEASUREMENT SUCCESSFULLY COMPLETED' in ps.stdout,\
        Tests.assertion_info('MEASUREMENT SUCCESSFULLY COMPLETED', ps.stdout)

def test_simple_run_job_missing_filename_branch():
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    machine_id = 1

    with pytest.raises(RuntimeError):
        Job.insert('run', user_id=1, name=name, url=url, machine_id=machine_id)


def test_simple_run_job_wrong_machine_id():
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'main'
    machine_id = 100

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        Job.insert('run', user_id=1, name=name, url=url, branch=branch, filename=filename, machine_id=machine_id)

def test_measurement_quota_exhausted():
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'main'
    machine_id = 1

    Job.insert('run', user_id=1, name=name, url=url, branch=branch, filename=filename, machine_id=machine_id)

    user = User(1)
    user._capabilities['measurement']['quotas'] = {'1': 2678400}
    user.update()
    user.deduct_measurement_quota(machine_id=machine_id, amount=2678400)

    ps = subprocess.run(
        ['python3', '../cron/jobs.py', 'run', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/../test-config.yml"],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    assert 'Your user does not have enough measurement quota to run a job on the selected machine. Machine ID: 1' in ps.stderr, Tests.assertion_info('Quota exhaused', ps.stderr)

def test_machine_not_allowed():
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'main'
    machine_id = 1
    Job.insert('run', user_id=1, name=name, url=url, branch=branch, filename=filename, machine_id=machine_id)

    user = User(1)
    user._capabilities['machines'] = []
    user.update()

    ps = subprocess.run(
        ['python3', '../cron/jobs.py', 'run', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/../test-config.yml"],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    assert 'Your user does not have the permissions to use the selected machine. Machine ID: 1' in ps.stderr, Tests.assertion_info('Machine forbidden', ps.stderr)



#pylint: disable=unused-variable # for the time being, until I get the mocking to work
## This test doesn't really make sense anymore as is, since we don't have "email jobs" in the same way,
## more that we send an email after a run job is finished.
def todo_test_simple_email_job():
    subject = utils.randomword(12)
    email = 'fakeemailaddress'
    message = 'simple job'

    Job.insert(
        'email-simple',
        user_id=1,
        email=email,
        name=subject,
        message=message,
    )

    # Why is this patch not working :-(
    with patch('email_helpers.send_email') as send_email:
        ps = subprocess.run(
                ['python3', '../cron/jobs.py', 'email-simple', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/../test-config.yml"],
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding='UTF-8'
            )
        #send_email.assert_called_with(email, pid)
    assert ps.stderr == '', Tests.assertion_info('No Error', f"STDOUT:\n{ps.stdout}\nSTDERR:\n{ps.stderr}")
    job_success_message = 'Successfully processed jobs queue item.'
    assert job_success_message in ps.stdout,\
       Tests.assertion_info('Successfully processed jobs queue item.', f"STDOUT:\n{ps.stdout}\nSTDERR:\n{ps.stderr}")


def test_docker_pull_private_image_via_db_credentials():
    if not os.getenv('GMT_TESTING_DOCKER_USER') or not os.getenv('GMT_TESTING_DOCKER_PAT'):
        raise RuntimeError('To run this test you need to set ENV vars GMT_TESTING_DOCKER_USER and GMT_TESTING_DOCKER_PAT - Can be ignored if you are submitting a PR as external developer as only the repo owners know these credentials.')

    Tests.shorten_sleep_times(1)

    name = utils.randomword(12)
    url = 'https://github.com/green-coding-solutions/green-metrics-tool'
    filename = 'tests/data/usage_scenarios/docker_pull_private_image.yml'
    branch = 'main'
    machine_id = 1

    job_id = Job.insert('run', user_id=1, name=name, url=url, branch=branch, filename=filename, machine_id=machine_id)

    # Store credentials encrypted in the DB — this is what the API endpoint does
    User(1).update_docker_credentials([{
        'registry': 'https://index.docker.io/v1/',
        'username': os.getenv('GMT_TESTING_DOCKER_USER'),
        'password': os.getenv('GMT_TESTING_DOCKER_PAT'),
    }])

    ps = subprocess.run(
        ['python3', '../cron/jobs.py', 'run', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/../test-config.yml"],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    assert 'Pulling greencoding/simple-test' in ps.stdout # step in question
    assert 'Saving image and volume sizes' in ps.stdout # step after
    # error after
    assert "'docker', 'run', '-it', '-d', '--name', 'test_service'" in ps.stderr
    assert 'returned non-zero exit status 125.' in ps.stderr
