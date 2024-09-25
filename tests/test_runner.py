from contextlib import nullcontext as does_not_raise

import pytest
import re
import os

from runner import Runner
from lib.global_config import GlobalConfig
from lib.system_checks import ConfigurationCheckError
from tests import test_functions as Tests

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')

GlobalConfig().override_config(config_name='test-config.yml')

test_data = [
   (True, does_not_raise()),
   (False, pytest.raises(ConfigurationCheckError)),
]

@pytest.mark.parametrize("skip_system_checks,expectation", test_data)
def test_check_system(skip_system_checks, expectation):
    runner = Runner(uri="not_relevant", uri_type="folder", skip_system_checks=skip_system_checks)

    if GlobalConfig().config['measurement']['metric-providers']['common'] is None:
        GlobalConfig().config['measurement']['metric-providers']['common'] = {}

    GlobalConfig().config['measurement']['metric-providers']['common']['psu.energy.ac.foo.machine.provider.SomeProvider'] = {
                'key': 'value'
            }
    GlobalConfig().config['measurement']['metric-providers']['common']['psu.energy.ac.bar.machine.provider.SomeOtherProvider'] = {
                'key': 'value'
            }
    try:
        with expectation:
            runner.check_system()
    finally:
        del GlobalConfig().config['measurement']['metric-providers']['common']['psu.energy.ac.foo.machine.provider.SomeProvider']
        del GlobalConfig().config['measurement']['metric-providers']['common']['psu.energy.ac.bar.machine.provider.SomeOtherProvider']

def test_reporters_still_running():
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=False, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=False)
    runner2 = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=False, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=False)


    with Tests.RunUntilManager(runner) as context:

        context.run_until('setup_services')

        with Tests.RunUntilManager(runner2) as context2:

            with pytest.raises(Exception) as e:
                context2.run_until('import_metric_providers')

            expected_error = r'Another instance of the \w+ metrics provider is already running on the system!\nPlease close it before running the Green Metrics Tool.'
            assert re.match(expected_error, str(e.value)), Tests.assertion_info(expected_error, str(e.value))
