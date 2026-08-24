import pytest

from lib import utils
from lib.encryption import ENCRYPTED_VALUE_PREFIX, decrypt_data, encrypt_data

@pytest.mark.parametrize('key,expected', [
    ('__GMT_VAR_SECRET_PASSWORD__', True),
    ('__GMT_VAR_SECRET_DB_PASSWORD__', True),
    ('__GMT_VAR_SECRET___', False), # the marker needs an actual name behind it
    ('__GMT_VAR_PASSWORD__', False),
    ('__GMT_VAR_MY_SECRET_PASSWORD__', False), # the marker only counts directly after the prefix
    ('__GMT_VAR_secret_PASSWORD__', False), # case sensitive, as is the rest of the variable syntax
])
def test_is_secret_usage_scenario_variable(key, expected):
    assert utils.is_secret_usage_scenario_variable(key) is expected

def test_encrypt_and_decrypt_secret_usage_scenario_variables():
    variables = {'__GMT_VAR_COMMAND__': 'stress-ng', '__GMT_VAR_SECRET_PASSWORD__': 'supersecret123'}

    encrypted_variables = utils.encrypt_secret_usage_scenario_variables(variables)

    assert encrypted_variables['__GMT_VAR_COMMAND__'] == 'stress-ng'
    assert encrypted_variables['__GMT_VAR_SECRET_PASSWORD__'].startswith(ENCRYPTED_VALUE_PREFIX)
    assert decrypt_data(encrypted_variables['__GMT_VAR_SECRET_PASSWORD__']) == 'supersecret123'

    assert utils.decrypt_secret_usage_scenario_variables(encrypted_variables) == variables

def test_encrypt_secret_usage_scenario_variables_leaves_encrypted_values_alone():
    encrypted_variables = {'__GMT_VAR_SECRET_PASSWORD__': encrypt_data('supersecret123')}

    assert utils.encrypt_secret_usage_scenario_variables(encrypted_variables) == encrypted_variables

def test_decrypt_secret_usage_scenario_variables_leaves_plaintext_alone():
    # secrets supplied directly on the CLI never went through encryption in the first place
    variables = {'__GMT_VAR_SECRET_PASSWORD__': 'supersecret123'}

    assert utils.decrypt_secret_usage_scenario_variables(variables) == variables

def test_redact_secret_usage_scenario_variables():
    variables = {'__GMT_VAR_COMMAND__': 'stress-ng', '__GMT_VAR_SECRET_PASSWORD__': 'supersecret123'}

    assert utils.redact_secret_usage_scenario_variables(variables) == {
        '__GMT_VAR_COMMAND__': 'stress-ng',
        '__GMT_VAR_SECRET_PASSWORD__': utils.REDACTED,
    }

def test_registered_sensitive_values_are_filtered():
    try:
        utils.register_sensitive_values(['supersecret123'])

        assert utils.filter_sensitive_data('psql --password supersecret123') == f"psql --password {utils.REDACTED}"
        assert utils.filter_sensitive_data_structure({'flow': [{'command': 'echo supersecret123'}]}) == {'flow': [{'command': f"echo {utils.REDACTED}"}]}
    finally:
        utils.clear_sensitive_values()

def test_short_sensitive_values_are_filtered():
    try:
        utils.register_sensitive_values(['a'])

        assert utils.filter_sensitive_data('secret=a') == f'secret={utils.REDACTED}'
    finally:
        utils.clear_sensitive_values()
