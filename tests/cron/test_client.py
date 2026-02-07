import os
import subprocess
from pathlib import Path

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import utils
from lib.job.base import Job
from tests import test_functions as Tests

def test_simple_cluster_run():

    tmp_folder = Path('/tmp/green-metrics-tool').resolve()
    tmp_folder.mkdir(exist_ok=True)

    name = utils.randomword(12)
    url = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'main'
    machine_id = 1

    Tests.shorten_sleep_times(1)

    Job.insert('run', user_id=1, name=name, url=url, branch=branch, filename=filename, machine_id=machine_id)

    ps = subprocess.run(
            ['python3', '../cron/client.py', '--testing', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/../test-config.yml"],
            check=False,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )

    assert ps.returncode == 0, f"Return code was not 0 but {ps.returncode}. Stderr: {ps.stderr}"
    assert ps.stderr == '', ps.stderr
    assert 'Successfully ended testing run of client.py' in ps.stdout,\
        Tests.assertion_info('Successfully ended testing run of client.py', ps.stdout)

    assert 'MEASUREMENT SUCCESSFULLY COMPLETED' in ps.stdout,\
        Tests.assertion_info('MEASUREMENT SUCCESSFULLY COMPLETED', ps.stdout)

    # also check that the tmp folder was deleted locally
    assert not tmp_folder.exists(), '/tmp/green-metrics-tool was still present after cluster run. It should have been deleted though'
