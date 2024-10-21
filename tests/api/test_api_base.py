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
    assert response.text == '{"success":false,"err":"Invalid token"}'

def test_alternative_user():
    Tests.insert_user(300, 'PYTEST')

    response = requests.get(f"{API_URL}/v1/authentication/data", timeout=15, headers={'X-Authentication': 'PYTEST'})
    assert response.status_code == 200
    assert json.loads(response.text)['data']['_name'] == 'PYTEST'
