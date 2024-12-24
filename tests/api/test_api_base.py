import json
import os
import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.user import User
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

def test_route_forbidden():
    user = User(1)
    user._capabilities['api']['routes'] = []
    user.update()

    response = requests.get(f"{API_URL}/v1/authentication/data", timeout=15)
    assert response.status_code == 401
    assert response.text == '{"success":false,"err":"Route not allowed"}'

# This method is just a safe-guard in case FastAPI ever changes the mechanic that an authentication parameter
# can be overriden through a simple query string
def test_no_user_query_string_override():
    response = requests.get(f"{API_URL}/v1/authentication/data?user=2", timeout=15)

    assert response.status_code == 200
    json_data = json.loads(response.text)

    assert json_data['success'] is True
    assert json_data['data']['_name'] == 'DEFAULT'


def test_can_read_authentication_data():
    response = requests.get(f"{API_URL}/v1/authentication/data", timeout=15)
    assert response.status_code == 200
    json_data = json.loads(response.text)

    assert json_data['success'] is True
    assert json_data['data'].get('_id', None) is None # must be deleted in response
    assert json_data['data']['_name'] == 'DEFAULT'

def test_api_quota_exhausted():
    user = User(1)
    user._capabilities['api']['quotas'] = {'/v1/authentication/data': 0}
    user.update()

    response = requests.get(f"{API_URL}/v1/authentication/data", timeout=15)
    assert response.status_code == 401
    assert response.text == '{"success":false,"err":"Quota exceeded"}'


def test_wrong_authentication():
    response = requests.get(f"{API_URL}/v1/authentication/data", timeout=15, headers={'X-Authentication': 'Asd'})
    assert response.status_code == 401
    assert response.text == '{"success":false,"err":"User with corresponding token not found"}'

def test_alternative_user():
    Tests.insert_user(300, 'PYTEST')

    response = requests.get(f"{API_URL}/v1/authentication/data", timeout=15, headers={'X-Authentication': 'PYTEST'})
    assert response.status_code == 200
    assert json.loads(response.text)['data']['_name'] == 'PYTEST'

def test_authenticate_with_empty_token_will_return_default():
    response = requests.get(f"{API_URL}/v1/authentication/data", timeout=15, headers={'X-Authentication': ''})
    assert response.status_code == 200
    json_data = json.loads(response.text)

    assert json_data['success'] is True
    assert json_data['data'].get('_id', None) is None # must be deleted in response
    assert json_data['data']['_name'] == 'DEFAULT'

def test_even_if_token_set_for_user_zero_api_will_still_fail():
    Tests.update_user_token(0, 'asd')
    response = requests.get(f"{API_URL}/v1/authentication/data", timeout=15, headers={'X-Authentication': 'asd'})
    assert response.status_code == 401

    json_data = json.loads(response.text)

    assert json_data['err'] == 'User 0 is system user and cannot log in'
