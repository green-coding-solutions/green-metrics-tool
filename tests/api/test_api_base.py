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
    assert response.text == '{"success":true,"data":{"_id":1,"_name":"DEFAULT","_capabilities":{"api":{"quotas":{},"routes":["/v2/carbondb/filters","/v2/carbondb","/v2/carbondb/add","/v1/ci/measurement/add","/v1/software/add","/v1/hog/add","/v1/authentication/data"]},"data":{"runs":{"retention":2678400},"hog_tasks":{"retention":2678400},"measurements":{"retention":2678400},"hog_coalitions":{"retention":2678400},"ci_measurements":{"retention":2678400},"hog_measurements":{"retention":2678400}},"jobs":{"schedule_modes":["one-off","daily","weekly","commit","variance"]},"machines":[1],"measurement":{"quotas":{},"settings":{"total-duration":86400,"flow-process-duration":86400}},"optimizations":["container_memory_utilization","container_cpu_utilization","message_optimization","container_build_time","container_boot_time","container_image_size"]}}}'

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
    assert json.loads(response.text)['data']['_id'] == 300
