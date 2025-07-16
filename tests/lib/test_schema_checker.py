import os
import yaml
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from schema import SchemaError

from lib.schema_checker import SchemaChecker
from tests import test_functions as Tests


def test_schema_checker_valid():
    usage_scenario_name = 'schema_checker_valid.yml'
    usage_scenario_path = os.path.join(CURRENT_DIR, '../data/usage_scenarios/schema_checker/', usage_scenario_name)
    with open(usage_scenario_path, encoding='utf8') as file:
        usage_scenario = yaml.safe_load(file)
    schema_checker = SchemaChecker(validate_compose_flag=True)
    schema_checker.check_usage_scenario(usage_scenario)

def test_schema_checker_both_network_types_valid():
    ## Check first that it works in case a, with the network listed as keys
    usage_scenario_name_a = 'schema_checker_valid_network_as_keys.yml'
    usage_scenario_path_a = os.path.join(CURRENT_DIR, '../data/usage_scenarios/schema_checker/', usage_scenario_name_a)
    with open(usage_scenario_path_a, encoding='utf8') as file:
        usage_scenario_a = yaml.safe_load(file)
    schema_checker_a = SchemaChecker(validate_compose_flag=True)
    schema_checker_a.check_usage_scenario(usage_scenario_a)

    ## Also check that it works in case b, with the networks as a list
    usage_scenario_name_b = 'schema_checker_valid_network_as_list.yml'
    usage_scenario_path_b = os.path.join(CURRENT_DIR, '../data/usage_scenarios/schema_checker/', usage_scenario_name_b)
    with open(usage_scenario_path_b, encoding='utf8') as file:
        usage_scenario_b = yaml.safe_load(file)
    schema_checker_b = SchemaChecker(validate_compose_flag=True)
    schema_checker_b.check_usage_scenario(usage_scenario_b)


def test_schema_checker_labels_valid():
    usage_scenario_name_dict = 'schema_checker_valid_labels_as_dict.yml'
    usage_scenario_path_dict = os.path.join(CURRENT_DIR, '../data/usage_scenarios/schema_checker/', usage_scenario_name_dict)
    with open(usage_scenario_path_dict, encoding='utf8') as file:
        usage_scenario_dict = yaml.safe_load(file)
    schema_checker_dict = SchemaChecker(validate_compose_flag=True)
    schema_checker_dict.check_usage_scenario(usage_scenario_dict)

    usage_scenario_name_list = 'schema_checker_valid_labels_as_list.yml'
    usage_scenario_path_list = os.path.join(CURRENT_DIR, '../data/usage_scenarios/schema_checker/', usage_scenario_name_list)
    with open(usage_scenario_path_list, encoding='utf8') as file:
        usage_scenario_list = yaml.safe_load(file)
    schema_checker_list = SchemaChecker(validate_compose_flag=True)
    schema_checker_list.check_usage_scenario(usage_scenario_list)


def test_schema_checker_network_alias():
    usage_scenario_name = 'schema_checker_valid_network_alias.yml'
    usage_scenario_path = os.path.join(CURRENT_DIR, '../data/usage_scenarios/schema_checker/', usage_scenario_name)
    with open(usage_scenario_path, encoding='utf8') as file:
        usage_scenario = yaml.safe_load(file)
    schema_checker = SchemaChecker(validate_compose_flag=True)
    schema_checker.check_usage_scenario(usage_scenario)


def test_schema_checker_invalid_network_alias():
    usage_scenario_name = 'schema_checker_invalid_network_alias.yml'
    usage_scenario_path = os.path.join(CURRENT_DIR, '../data/usage_scenarios/schema_checker/', usage_scenario_name)
    with open(usage_scenario_path, encoding='utf8') as file:
        usage_scenario = yaml.safe_load(file)
    schema_checker = SchemaChecker(validate_compose_flag=True)
    with pytest.raises(SchemaError) as error:
        schema_checker.check_usage_scenario(usage_scenario)
    expected_exception = "bad!alias includes disallowed values: ['!']"
    assert expected_exception in str(error.value), \
        Tests.assertion_info(f"Exception: {expected_exception}", str(error.value))


def test_schema_checker_invalid_missing_description():
    usage_scenario_name = 'schema_checker_invalid_missing_description.yml'
    usage_scenario_path = os.path.join(CURRENT_DIR, '../data/usage_scenarios/schema_checker/', usage_scenario_name)
    with open(usage_scenario_path, encoding='utf8') as file:
        usage_scenario = yaml.safe_load(file)

    schema_checker = SchemaChecker(validate_compose_flag=True)
    with pytest.raises(SchemaError) as error:
        schema_checker.check_usage_scenario(usage_scenario)

    expected_exception = "Missing key: 'description'"
    assert expected_exception in str(error.value), \
        Tests.assertion_info(expected_exception, str(error.value))


def test_schema_checker_invalid_image_req_when_no_build():
    usage_scenario_name = 'schema_checker_invalid_image_builds.yml'
    usage_scenario_path = os.path.join(CURRENT_DIR, '../data/usage_scenarios/schema_checker/', usage_scenario_name)
    with open(usage_scenario_path, encoding='utf8') as file:
        usage_scenario = yaml.safe_load(file)

    schema_checker = SchemaChecker(validate_compose_flag=True)
    with pytest.raises(SchemaError) as error:
        schema_checker.check_usage_scenario(usage_scenario)

    expected_exception = "The 'image' key for service 'test-container' is required when 'build' key is not present."
    assert expected_exception in str(error.value), \
        Tests.assertion_info(f"Exception: {expected_exception}", str(error.value))

def test_schema_checker_invalid_wrong_type():
    usage_scenario_name = 'schema_checker_invalid_wrong_type.yml'
    usage_scenario_path = os.path.join(CURRENT_DIR, '../data/usage_scenarios/schema_checker/', usage_scenario_name)
    with open(usage_scenario_path, encoding='utf8') as file:
        usage_scenario = yaml.safe_load(file)

    schema_checker = SchemaChecker(validate_compose_flag=True)
    with pytest.raises(SchemaError) as error:
        schema_checker.check_usage_scenario(usage_scenario)

    expected_exception = "Key 'log-stderr' error:\n'no' should be instance of 'bool'"
    print(error.value)
    assert expected_exception in str(error.value), \
        Tests.assertion_info(f"Exception: {expected_exception}", str(error.value))
