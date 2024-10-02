import os
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import utils
from lib.global_config import GlobalConfig
from lib.job.base import Job
from tests import test_functions as Tests

GlobalConfig().override_config(config_name='test-config.yml')
config = GlobalConfig().config

def test_simple_cluster_run():
    name = utils.randomword(12)
    url = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    branch = 'main'
    machine_id = 1

    Job.insert('run', user_id=1, name=name, url=url, email=None, branch=branch, filename=filename, machine_id=machine_id)

    ps = subprocess.run(
            ['python3', '../cron/client.py', '--testing', '--config-override', 'test-config.yml'],
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
