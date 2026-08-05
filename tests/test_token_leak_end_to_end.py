import io
import json
import os

from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import pytest
import yaml

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib import utils
from lib.global_config import GlobalConfig
from tests import test_functions as Tests
from lib.scenario_runner import ScenarioRunner

TOKEN_SENTINEL = 'SUPER_SECRET_TOKEN_END_TO_END_DO_NOT_LEAK'
RUN_NAME = 'test_token_leak_' + utils.randomword(12)

BASE_CONFIG_PATH = Path(CURRENT_DIR) / 'test-config.yml'
TMP_CONFIG_PATH = Path(CURRENT_DIR) / f'test-config-token-leak-{utils.randomword(8)}.yml'


#pylint: disable=unused-argument
@pytest.fixture(autouse=True, scope='module')
def setup_and_cleanup_test():
    with BASE_CONFIG_PATH.open(encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    cfg['measurement'].setdefault('metric_providers', {})
    cfg['measurement']['metric_providers'].setdefault('common', {})
    cfg['measurement']['metric_providers']['common']['carbon_intensity_electricitymaps_machine'] = {
        'region': 'DE',
        'token': TOKEN_SENTINEL,
    }

    TMP_CONFIG_PATH.write_text(yaml.safe_dump(cfg), encoding='utf-8')
    GlobalConfig().override_config(config_location=str(TMP_CONFIG_PATH))

    yield

    TMP_CONFIG_PATH.unlink(missing_ok=True)
    GlobalConfig().override_config(config_location=str(BASE_CONFIG_PATH))
    Tests.reset_db()


#pylint: disable=expression-not-assigned,global-statement
def setup_module(module):
    # We deliberately keep dev_no_metrics=True: this skips the live Electricity Maps API call (which
    # would fail with our sentinel token) but still exercises _initialize_run, which is the leak path
    # being guarded - it serialises configured_metric_providers (including the token) into the runs row.
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        folder = 'tests/data/stress-application/'
        filename = 'usage_scenario.yml'

        runner = ScenarioRunner(
            name=RUN_NAME, uri=GMT_DIR, filename=folder + filename, uri_type='folder',
            dev_cache_build=False, dev_no_sleeps=True,
            dev_no_metrics=True, dev_no_system_checks=True,
            dev_no_container_dependency_collection=True,
            measurement_pre_test_sleep=0, measurement_baseline_duration=0, measurement_idle_duration=0,
            measurement_post_test_sleep=0, measurement_phase_transition_time=0, measurement_wait_time_dependencies=0,
        )
        runner.run()


def test_electricity_maps_token_is_not_in_runs_row():
    run_id = utils.get_run_data(RUN_NAME)['id']
    run_row = DB().fetch_one(
        'SELECT * FROM runs WHERE id = %s', params=(run_id,), fetch_mode='dict',
    )

    assert run_row is not None, f'No runs row found for {RUN_NAME}'
    assert TOKEN_SENTINEL not in json.dumps(run_row, default=str), (
        f'Electricity Maps token leaked into the runs table for run {run_id}'
    )


def test_electricity_maps_token_is_redacted_in_configured_metric_providers():
    # Stronger assertion: the configured_metric_providers section was actually populated for
    # electricity_maps and the token value was replaced with the sanitiser placeholder.
    run_id = utils.get_run_data(RUN_NAME)['id']
    measurement_config = DB().fetch_one(
        'SELECT measurement_config FROM runs WHERE id = %s', params=(run_id,),
    )[0]

    configured = measurement_config.get('configured_metric_providers') or {}
    em = configured.get('carbon_intensity_electricitymaps_machine')
    assert em is not None, (
        f'Expected electricity_maps provider to appear in configured_metric_providers; got: {configured}'
    )
    assert em.get('token') != TOKEN_SENTINEL, f'Token was stored verbatim: {em}'
    assert em.get('region') == 'DE', f'Non-sensitive fields should remain intact: {em}'
