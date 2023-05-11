#pylint: disable=import-error, wrong-import-position

import os
import sys
import yaml
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/../..")
sys.path.append(f"{CURRENT_DIR}/../../lib")

from schema import SchemaError
from schema_checker import check_usage_scenario
import test_functions as Tests


def test_schema_checker_valid():
    usage_scenario_name = 'schema_checker_valid.yml'
    usage_scenario_path = os.path.join(CURRENT_DIR, '../data/usage_scenarios/', usage_scenario_name)
    with open(usage_scenario_path, encoding='utf8') as file:
        usage_scenario = yaml.safe_load(file)
    check_usage_scenario(usage_scenario)

def test_schema_checker_invalid():
    usage_scenario_name = 'schema_checker_invalid_1.yml'
    usage_scenario_path = os.path.join(CURRENT_DIR, '../data/usage_scenarios/', usage_scenario_name)
    with open(usage_scenario_path, encoding='utf8') as file:
        usage_scenario = yaml.safe_load(file)

    with pytest.raises(SchemaError) as error:
        check_usage_scenario(usage_scenario)

    expected_exception = "Missing key: 'description'"
    assert expected_exception in str(error.value), \
        Tests.assertion_info(f"Exception: {expected_exception}", str(error.value))
