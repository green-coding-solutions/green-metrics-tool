import os
import sys
from shutil import copy2

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DATA_CONFIG_DIR = os.path.join(CURRENT_DIR, "data", "config_files")
REPO_ROOT = os.path.realpath(os.path.join(CURRENT_DIR, ".."))
sys.path.append(f"{CURRENT_DIR}/../.")
sys.path.append(f"{CURRENT_DIR}/../lib/")

#pylint:disable=import-error
from runner import Runner
from global_config import GlobalConfig


test_data = [
    ("two_psu_providers.yml", True, True),
    ("two_psu_providers.yml", False, False),
]

@pytest.mark.parametrize("config_file,skip_config_check,expected_return", test_data)
def test_check_configuration(config_file, skip_config_check, expected_return):

    runner = Runner("foo", "baz", "bar", skip_config_check=skip_config_check)
    copy2(os.path.join(TEST_DATA_CONFIG_DIR, config_file), os.path.join(REPO_ROOT, config_file))
    GlobalConfig(config_name=config_file)

    ret = runner.check_configuration()

    os.remove(os.path.join(REPO_ROOT, config_file))

    assert ret == expected_return
