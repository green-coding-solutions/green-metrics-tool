import os
import requests
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

def test_ci_deprecated_endpoint():
    response = requests.post(f"{API_URL}/v1/ci/measurement/add", json={}, timeout=15)
    assert response.status_code == 410, Tests.assertion_info('success', response.text)

MEASUREMENT_MODEL_NEW = {'energy_uj': 123000,
                        'repo': 'testRepo',
                        'branch': 'testBranch',
                        'cpu': 'testCPU',
                        'cpu_util_avg': 50,
                        'commit_hash': '1234asdf',
                        'workflow': 'testWorkflow',
                        'run_id': 'testRunID',
                        'source': 'testSource',
                        'label': 'testLabel',
                        'duration_us': 20000,
                        'workflow_name': 'testWorkflowName'}

MEASUREMENT_MODEL_V3 = {'energy_uj': 123000,
                        'repo': 'testRepo',
                        'branch': 'testBranch',
                        'cpu': 'testCPU',
                        'cpu_util_avg': 50,
                        'commit_hash': '1234asdf',
                        'workflow': 'testWorkflow',
                        'run_id': 'testRunID',
                        'source': 'testSource',
                        'label': 'testLabel',
                        'duration_us': 20000,
                        'workflow_name': 'testWorkflowName',
                        'os_name': 'testOsName',
                        'cpu_arch': 'testCpuArch',
                        'job_id': 'testJobID'}

def test_ci_measurement_add_default_user():

    measurement_model = MEASUREMENT_MODEL_NEW.copy()

    response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_carbondb_data(measurement_model, data)

    assert data['user_id'] == 1
    # assert the defaults set by the model
    assert data['filter_type'] == 'machine.ci'
    assert data['filter_machine'] == 'unknown'
    assert data['filter_project'] == 'CI/CD'
    assert data['filter_tags'] == []

def test_ci_measurement_add_different_user():

    Tests.insert_user(2, 'PYTEST')

    measurement_model = MEASUREMENT_MODEL_NEW.copy()

    response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement_model, timeout=15, headers={'X-Authentication': 'PYTEST'})
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_carbondb_data(measurement_model, data)

    assert data['user_id'] == 2


def test_ci_measurement_add_co2():

    measurement_model = MEASUREMENT_MODEL_NEW.copy()

    measurement_model['lat'] = '18.2972'
    measurement_model['lon'] = '77.2793'
    measurement_model['city'] = 'Nine Mile'
    measurement_model['carbon_intensity_g'] = 100
    measurement_model['carbon_ug'] = 4567893453245

    response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_carbondb_data(measurement_model, data)


def test_ci_measurement_add_small_with_warning():

    measurement_model = MEASUREMENT_MODEL_NEW.copy()
    measurement_model['energy_uj'] = 1

    response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)
    logs = subprocess.check_output(['docker', 'logs', 'test-green-coding-gunicorn-container', '-n', '10'], stderr=subprocess.STDOUT, encoding='UTF-8').strip()

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_carbondb_data(measurement_model, data)


    assert 'Extremely small energy budget was submitted to Eco CI API' in logs
    assert 'Measurement (CI_Measurement): energy_uj=1' in logs

def test_ci_measurement_add_force_ip():

    measurement_model = MEASUREMENT_MODEL_NEW.copy()
    measurement_model['ip'] = '1.1.1.1'

    response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])

    data['ip'] = str(data['ip_address']) # model as a different key in DB
    del data['ip_address']

    compare_carbondb_data(measurement_model, data)

def test_ci_measurement_add_filters():

    measurement_model = MEASUREMENT_MODEL_NEW.copy()

    measurement_model['filter_tags'] = ["asd", "Mit space"]
    measurement_model['filter_project'] = 'Das ist cool'
    measurement_model['filter_type'] = 'CI / CD'

    response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_carbondb_data(measurement_model, data)

def test_ci_badge_duration_error():
    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=avg&duration_days=900", timeout=15)
    assert response.status_code == 422
    assert response.text == '{"success":false,"err":"Duration days must be between 1 and 365 days","body":null}'


def test_ci_badge_get_last():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=last", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Last run energy used' in response.text, Tests.assertion_info('success', response.text)
    assert '8.04 mWh' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=last&unit=joules", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Last run energy used' in response.text, Tests.assertion_info('success', response.text)
    assert '28.95 J' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=last&metric=carbon", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Last run carbon emitted' in response.text, Tests.assertion_info('success', response.text)
    assert '0.02 g' in response.text, Tests.assertion_info('success', response.text)


def test_ci_badge_get_totals():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=totals", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'All runs total energy used' in response.text, Tests.assertion_info('success', response.text)
    assert '13617.37 mWh' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=totals&unit=joules", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'All runs total energy used' in response.text, Tests.assertion_info('success', response.text)
    assert '49022.55 J' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=totals&metric=carbon", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'All runs total carbon emitted' in response.text, Tests.assertion_info('success', response.text)
    assert '15.56 g' in response.text, Tests.assertion_info('success', response.text)


def test_ci_badge_get_average():

    for i in range(1,3):
        measurement_model = MEASUREMENT_MODEL_NEW.copy()
        measurement_model['carbon_ug'] = 1000
        response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement_model, timeout=15)
        assert response.status_code == 204, Tests.assertion_info('success', response.text)

    for i in range(1,6):
        measurement_model = MEASUREMENT_MODEL_NEW.copy()
        measurement_model['energy_uj'] *= 1000
        measurement_model['carbon_ug'] = i*100000
        measurement_model['run_id'] = 'Other run'
        response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement_model, timeout=15)
        assert response.status_code == 204, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo={MEASUREMENT_MODEL_NEW['repo']}&branch={MEASUREMENT_MODEL_NEW['branch']}&workflow={MEASUREMENT_MODEL_NEW['workflow']}&mode=avg&duration_days=5&unit=joules", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Per run moving average (5 days) energy used' in response.text, Tests.assertion_info('success', response.text)
    assert '307.62 J' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo={MEASUREMENT_MODEL_NEW['repo']}&branch={MEASUREMENT_MODEL_NEW['branch']}&workflow={MEASUREMENT_MODEL_NEW['workflow']}&mode=avg&duration_days=5", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Per run moving average (5 days) energy used' in response.text, Tests.assertion_info('success', response.text)
    assert '85.45 mWh' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo={MEASUREMENT_MODEL_NEW['repo']}&branch={MEASUREMENT_MODEL_NEW['branch']}&workflow={MEASUREMENT_MODEL_NEW['workflow']}&mode=avg&duration_days=5&metric=carbon", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)

    assert 'Per run moving average (5 days) carbon emitted' in response.text, Tests.assertion_info('success', response.text)
    assert '0.75 g' in response.text, Tests.assertion_info('success', response.text)


def test_get_insights():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/ci/insights", timeout=15)
    res_json = response.json()
    assert response.status_code == 200
    assert res_json['data'][0] == 453
    assert res_json['data'][1] == '2023-08-01'

# tests for /v3/ci/measurement/add
def test_ci_measurement_add_default_user_v3():

    measurement_model = MEASUREMENT_MODEL_V3.copy()

    response = requests.post(f"{API_URL}/v3/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_carbondb_data(measurement_model, data)

    assert data['user_id'] == 1
    # assert the defaults set by the model
    assert data['filter_type'] == 'machine.ci'
    assert data['filter_machine'] == 'unknown'
    assert data['filter_project'] == 'CI/CD'
    assert data['filter_tags'] == []

def test_ci_measurement_add_different_user_v3():

    Tests.insert_user(2, 'PYTEST')

    measurement_model = MEASUREMENT_MODEL_V3.copy()

    response = requests.post(f"{API_URL}/v3/ci/measurement/add", json=measurement_model, timeout=15, headers={'X-Authentication': 'PYTEST'})
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_carbondb_data(measurement_model, data)

    assert data['user_id'] == 2


def test_ci_measurement_add_co2_v3():

    measurement_model = MEASUREMENT_MODEL_V3.copy()

    measurement_model['lat'] = '18.2972'
    measurement_model['lon'] = '77.2793'
    measurement_model['city'] = 'Nine Mile'
    measurement_model['carbon_intensity_g'] = 100
    measurement_model['carbon_ug'] = 4567893453245

    response = requests.post(f"{API_URL}/v3/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_carbondb_data(measurement_model, data)


def test_ci_measurement_add_small_with_warning_v3():

    measurement_model = MEASUREMENT_MODEL_V3.copy()
    measurement_model['energy_uj'] = 1

    response = requests.post(f"{API_URL}/v3/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)
    logs = subprocess.check_output(['docker', 'logs', 'test-green-coding-gunicorn-container', '-n', '10'], stderr=subprocess.STDOUT, encoding='UTF-8').strip()

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_carbondb_data(measurement_model, data)


    assert 'Extremely small energy budget was submitted to Eco CI API' in logs
    assert 'Measurement (CI_MeasurementV3): energy_uj=1' in logs

def test_ci_measurement_add_force_ip_v3():

    measurement_model = MEASUREMENT_MODEL_V3.copy()
    measurement_model['ip'] = '1.1.1.1'

    response = requests.post(f"{API_URL}/v3/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])

    data['ip'] = str(data['ip_address']) # model as a different key in DB
    del data['ip_address']

    compare_carbondb_data(measurement_model, data)

def test_ci_measurement_add_filters_v3():

    measurement_model = MEASUREMENT_MODEL_V3.copy()

    measurement_model['filter_tags'] = ["asd", "Mit space"]
    measurement_model['filter_project'] = 'Das ist cool'
    measurement_model['filter_type'] = 'CI / CD'

    response = requests.post(f"{API_URL}/v3/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_carbondb_data(measurement_model, data)

## helpers

def fetch_data_from_db(run_id):
    query = 'SELECT * FROM ci_measurements WHERE run_id = %s' # we make * match to always test all columns. Even if we add some in the future. However they must be part of CI_Measurement
    return DB().fetch_one(query, (run_id, ), fetch_mode='dict')

def compare_carbondb_data(measurement_model, data):
    for key in measurement_model.keys():
        if key in['workflow']: continue
        assert key in data
        assert data[key] == measurement_model[key]
