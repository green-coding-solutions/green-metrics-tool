from contextlib import nullcontext as does_not_raise
import os
import sys
from shutil import copy2

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DATA_CONFIG_DIR = os.path.join(CURRENT_DIR, "data", "config_files")
REPO_ROOT = os.path.realpath(os.path.join(CURRENT_DIR, ".."))
sys.path.append(f"{CURRENT_DIR}/../.")
sys.path.append(f"{CURRENT_DIR}/../lib/")

#pylint:disable=import-error, wrong-import-position, wrong-import-order
from runner import Runner
from global_config import GlobalConfig


test_data = [
    ("two_psu_providers.yml", True, does_not_raise()),
    ("two_psu_providers.yml", False, pytest.raises(ValueError)),
]

@pytest.mark.parametrize("config_file,skip_config_check,expectation", test_data)
def test_check_configuration(config_file, skip_config_check, expectation):

    runner = Runner("foo", "baz", "bar", skip_config_check=skip_config_check)
    copy2(os.path.join(TEST_DATA_CONFIG_DIR, config_file), os.path.join(REPO_ROOT, config_file))
    GlobalConfig().override_config(config_name=config_file)
    try:
        with expectation:
            runner.check_configuration()
    finally:
        os.remove(os.path.join(REPO_ROOT, config_file))
