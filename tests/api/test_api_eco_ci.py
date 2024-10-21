import os
import requests
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

# TODO: Turn on once deprecated fully
#def test_ci_deprecated_endpoint():
#    response = requests.post(f"{API_URL}/v1/ci/measurement/add", json={}, timeout=15)
#    assert response.status_code == 410, Tests.assertion_info('success', response.text)


# We are using a dict here and not the Model itself as the model sets the defaults automatically
MEASUREMENT_MODEL_OLD = {'energy_value': 123,
                        'energy_unit': 'mJ',
                        'repo': 'testRepo',
                        'branch': 'testBranch',
                        'cpu': 'testCPU',
                        'cpu_util_avg': 50,
                        'commit_hash': '1234asdf',
                        'workflow': 'testWorkflow',
                        'run_id': 'testRunID',
                        'source': 'testSource',
                        'label': 'testLabel',
                        'duration': 5,
                        'workflow_name': 'testWorkflowName'}

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

def test_old_api():

    measurement_model = MEASUREMENT_MODEL_OLD.copy()
    response = requests.post(f"{API_URL}/v1/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])

    assert data['user_id'] == 1
    assert data['energy_uj'] == measurement_model['energy_value']*1_000
    assert data['run_id'] == measurement_model['run_id']
    assert data['source'] == measurement_model['source']

    assert data['duration_us'] == measurement_model['duration']*1_000_000

def test_old_api_with_co2():
    measurement_model = MEASUREMENT_MODEL_OLD.copy()
    measurement_model['co2i'] = '333'
    measurement_model['co2eq'] = '0.31321'

    response = requests.post(f"{API_URL}/v1/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])

    assert data['user_id'] == 1
    assert data['energy_uj'] == measurement_model['energy_value']*1_000
    assert data['run_id'] == measurement_model['run_id']
    assert data['source'] == measurement_model['source']
    assert data['duration_us'] == measurement_model['duration']*1_000_000

    assert data['carbon_ug'] == int(float(measurement_model['co2eq'])*1_000_000)
    assert data['carbon_intensity_g'] == int(measurement_model['co2i'])

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


    assert 'Extremely small energy budget was submitted to Eco-CI API' in logs
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

## helpers

def fetch_data_from_db(run_id):
    query = 'SELECT * FROM ci_measurements WHERE run_id = %s' # we make * match to always test all columns. Even if we add some in the future. However they must be part of CI_Measurement
    return DB().fetch_one(query, (run_id, ), fetch_mode='dict')

def compare_carbondb_data(measurement_model, data):
    for key in measurement_model.keys():
        if key in['workflow']: continue
        assert key in data
        assert data[key] == measurement_model[key]
