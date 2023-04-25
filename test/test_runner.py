import os
import sys

import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/../.")
sys.path.append(f"{CURRENT_DIR}/../lib/")

#pylint:disable=import-error
from runner import Runner
# from global_config import GlobalConfig


test_data = [
    (True, True),
    (False, True),
]

@pytest.mark.parametrize("skip_config_check,expected_return", test_data)
def test_check_configuration(skip_config_check, expected_return):

    runner = Runner("foo", "baz", "bar", skip_config_check=skip_config_check)

    # TODO: override config for tests? Found no test configs in test data
    # GlobalConfig(config_name="some.yml")
    # but it will look at repo root for it - why only repo root?

    ret = runner.check_configuration()

    assert ret == expected_return
