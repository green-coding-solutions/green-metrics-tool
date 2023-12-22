from contextlib import nullcontext as does_not_raise
import os
from shutil import copy2

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DATA_CONFIG_DIR = os.path.join(CURRENT_DIR, "data", "config_files")
REPO_ROOT = os.path.realpath(os.path.join(CURRENT_DIR, ".."))

from runner import Runner
from lib.global_config import GlobalConfig
from lib.system_checks import ConfigurationCheckError
from tests import test_functions as Tests
from lib.system_checks import check_providers_running

test_data = [
    ("two_psu_providers.yml", True, does_not_raise()),
    ("two_psu_providers.yml", False, pytest.raises(ConfigurationCheckError)),
]

@pytest.mark.parametrize("config_file,skip_system_checks,expectation", test_data)
def test_check_system(config_file, skip_system_checks, expectation):
    runner = Runner("foo", "baz", "bar", skip_system_checks=skip_system_checks)
    copy2(os.path.join(TEST_DATA_CONFIG_DIR, config_file), os.path.join(REPO_ROOT, config_file))
    GlobalConfig().override_config(config_name=config_file)
    try:
        with expectation:
            runner.check_system()
    finally:
        os.remove(os.path.join(REPO_ROOT, config_file))

def test_reporters_still_running():
    runner = Tests.setup_runner(usage_scenario='basic_stress.yml', skip_unsafe=True, dry_run=True)

    runner.check_system('start') # should not fail

    try:
        Tests.run_until(runner, 'setup_services')

        assert check_providers_running() is False, 'Providers where expected to be still running on system, but where not.'

    finally:
        Tests.cleanup(runner)
