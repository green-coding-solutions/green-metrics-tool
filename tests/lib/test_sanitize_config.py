import json
import os

import pytest

from lib import utils
from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_CONFIG_FILE = os.path.normpath(f"{CURRENT_DIR}/../test-config.yml")

TOKEN_SENTINEL = 'SUPER_SECRET_TOKEN_DO_NOT_LEAK'


@pytest.fixture(autouse=True)
def _restore_config():
    GlobalConfig().override_config(config_location=TEST_CONFIG_FILE)
    yield
    GlobalConfig().override_config(config_location=TEST_CONFIG_FILE)
    Tests.reset_db()


def test_sanitize_config_redacts_top_level_token():
    sanitized = utils.sanitize_config({'token': TOKEN_SENTINEL, 'region': 'DE'})
    assert sanitized['token'] != TOKEN_SENTINEL
    assert sanitized['region'] == 'DE'


def test_sanitize_config_redacts_nested_token():
    nested = {
        'carbon_intensity_electricitymaps_machine': {
            'region': 'DE',
            'token': TOKEN_SENTINEL,
        }
    }
    sanitized = utils.sanitize_config(nested)
    assert TOKEN_SENTINEL not in json.dumps(sanitized)
    assert sanitized['carbon_intensity_electricitymaps_machine']['region'] == 'DE'


def test_sanitize_config_redacts_inside_lists():
    payload = [{'token': TOKEN_SENTINEL}, {'password': TOKEN_SENTINEL}]
    sanitized = utils.sanitize_config(payload)
    assert TOKEN_SENTINEL not in json.dumps(sanitized)


def test_sanitize_config_redacts_deep_structure():
    payload = {
        'measurement': {
            'metric_providers': {
                'linux': {
                    'carbon_intensity_electricitymaps_machine': {
                        'region': 'DE',
                        'token': TOKEN_SENTINEL,
                    }
                }
            }
        }
    }
    sanitized = utils.sanitize_config(payload)
    assert TOKEN_SENTINEL not in json.dumps(sanitized)


def test_sanitize_config_is_case_insensitive_on_keys():
    sanitized = utils.sanitize_config({'Token': TOKEN_SENTINEL, 'PASSWORD': TOKEN_SENTINEL})
    assert TOKEN_SENTINEL not in json.dumps(sanitized)


def test_sanitize_config_leaves_non_sensitive_values_intact():
    payload = {'region': 'DE', 'sampling_rate': 99, 'nested': {'value': 'keep_me'}}
    assert utils.sanitize_config(payload) == payload


def test_sanitize_config_does_not_match_substrings():
    # Substring matching previously caused false positives; ensure keys merely *containing* "token" are not redacted
    payload = {'tokenizer_path': '/tmp/foo', 'token_count': 42}
    sanitized = utils.sanitize_config(payload)
    assert sanitized == payload


def _thaw(value):
    if isinstance(value, dict):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return value


def _config_with_token():
    config = _thaw(GlobalConfig().config)
    arch = utils.get_architecture()
    config['measurement']['metric_providers'].setdefault(arch, {})
    config['measurement']['metric_providers'][arch]['carbon_intensity_electricitymaps_machine'] = {
        'region': 'DE',
        'token': TOKEN_SENTINEL,
    }
    return config


def test_token_is_not_persisted_in_runs_measurement_config():
    # Emulates the relevant slice of ScenarioRunner._initialize_run to verify
    # that a token configured for a metric provider never lands in the runs table.
    config = _config_with_token()

    measurement_config = {
        'measurement_settings': utils.sanitize_config(
            {k: v for k, v in config['measurement'].items() if k != 'metric_providers'}
        ),
        'configured_metric_providers': utils.sanitize_config(utils.get_metric_providers(config)),
    }

    run_id = DB().fetch_one(
        '''
        INSERT INTO runs (uri, branch, filename, user_id, machine_id, measurement_config)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        ''',
        params=('test-uri', 'test-branch', 'test-filename', 1, 1, json.dumps(measurement_config)),
    )[0]

    run_row = DB().fetch_one(
        'SELECT * FROM runs WHERE id = %s', params=(run_id,), fetch_mode='dict'
    )

    assert TOKEN_SENTINEL not in json.dumps(run_row, default=str), (
        f'Electricity Maps token leaked into the runs table for run {run_id}'
    )


def test_token_is_not_persisted_in_machine_configuration():
    # Mirrors the payload built in cron/client.set_status before writing to machines.configuration.
    config = _config_with_token()

    payload = utils.sanitize_config({
        'measurement': config['measurement'],
        'machine': config['machine'],
        'cluster': config['cluster'],
    })

    DB().query(
        'UPDATE machines SET configuration = %s WHERE id = %s',
        params=(json.dumps(payload), config['machine']['id']),
    )

    machine_row = DB().fetch_one(
        'SELECT * FROM machines WHERE id = %s',
        params=(config['machine']['id'],),
        fetch_mode='dict',
    )

    assert TOKEN_SENTINEL not in json.dumps(machine_row, default=str), (
        'Electricity Maps token leaked into the machines.configuration column'
    )
