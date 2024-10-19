import os
import requests
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

from api.main import CI_Measurement

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

def test_ci_deprecated_endpoint():
    response = requests.post(f"{API_URL}/v1/ci/measurement/add", json={}, timeout=15)
    assert response.status_code == 410, Tests.assertion_info('success', response.text)


def test_ci_measurement_add_default_user():
    measurement = CI_Measurement(energy_uj=123,
                        repo='testRepo',
                        branch='testBranch',
                        cpu='testCPU',
                        cpu_util_avg=50,
                        commit_hash='1234asdf',
                        workflow='testWorkflow',
                        run_id='testRunID',
                        source='testSource',
                        label='testLabel',
                        duration_us=20000,
                        workflow_name='testWorkflowName')
    response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement.model_dump(), timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    query = 'SELECT * FROM ci_measurements WHERE run_id = %s' # we make * match to always test all columns. Even if we add some in the future. However they must be part of CI_Measurement
    data = DB().fetch_one(query, (measurement.run_id, ), fetch_mode='dict')

    ndata = {k: v for k, v in data.items() if k not in ['id', 'created_at', 'updated_at', 'workflow_id', 'workflow_name', 'user_id', 'filter_source', 'ip_address']}
    assert CI_Measurement(workflow_name=measurement.workflow_name, workflow=measurement.workflow, **ndata).model_dump() == measurement.model_dump()
    assert data['user_id'] == 1

def test_ci_measurement_add_different_user():
    measurement = CI_Measurement(energy_uj=123,
                        repo='testRepo',
                        branch='testBranch',
                        cpu='testCPU',
                        cpu_util_avg=50,
                        commit_hash='1234asdf',
                        workflow='testWorkflow',
                        run_id='testRunID',
                        source='testSource',
                        label='testLabel',
                        duration_us=20000,
                        workflow_name='testWorkflowName')

    Tests.insert_user(2, 'PYTEST')

    response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement.model_dump(), timeout=15, headers={'X-Authentication': 'PYTEST'})
    assert response.status_code == 200, Tests.assertion_info('success', response.text)

    query = 'SELECT * FROM ci_measurements WHERE run_id = %s' # we make * match to always test all columns. Even if we add some in the future. However they must be part of CI_Measurement
    data = DB().fetch_one(query, (measurement.run_id, ), fetch_mode='dict')

    ndata = {k: v for k, v in data.items() if k not in ['id', 'created_at', 'updated_at', 'workflow_id', 'workflow_name', 'user_id', 'filter_source', 'ip_address']}
    assert CI_Measurement(workflow_name=measurement.workflow_name, workflow=measurement.workflow, **ndata).model_dump() == measurement.model_dump()
    assert data['user_id'] == 2


def test_ci_measurement_add_co2():
    measurement = CI_Measurement(energy_uj=123,
                        repo='testRepo',
                        branch='testBranch',
                        cpu='testCPU',
                        cpu_util_avg=50,
                        commit_hash='1234asdf',
                        workflow='testWorkflow',
                        run_id='testRunID',
                        source='testSource',
                        label='testLabel',
                        duration_us=20000,
                        workflow_name='testWorkflowName',
                        lat="18.2972",
                        lon="77.2793",
                        city="Nine Mile",
                        carbon_intensity_g=100,
                        carbon_ug=4567893453245)

    response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement.model_dump(), timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    query = 'SELECT * FROM ci_measurements WHERE run_id = %s' # we make * match to always test all columns. Even if we add some in the future. However they must be part of CI_Measurement
    data = DB().fetch_one(query, (measurement.run_id, ), fetch_mode='dict')

    ndata = {k: v for k, v in data.items() if k not in ['id', 'created_at', 'updated_at', 'workflow_id', 'workflow_name', 'user_id', 'filter_source', 'ip_address']}
    assert CI_Measurement(workflow_name=measurement.workflow_name, workflow=measurement.workflow, **ndata).model_dump() == measurement.model_dump()


def test_ci_measurement_add_small_with_warning():
    measurement = CI_Measurement(energy_uj=1,
                        repo='testRepo',
                        branch='testBranch',
                        cpu='testCPU',
                        cpu_util_avg=50,
                        commit_hash='1234asdf',
                        workflow='testWorkflow',
                        run_id='testRunID',
                        source='testSource',
                        label='testLabel',
                        duration_us=20000,
                        workflow_name='testWorkflowName',
                        lat="18.2972",
                        lon="77.2793",
                        city="Nine Mile",
                        carbon_intensity_g=100,
                        carbon_ug=7893453245)

    response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement.model_dump(), timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    logs = subprocess.check_output(['docker', 'logs', 'test-green-coding-gunicorn-container', '-n', '10'], stderr=subprocess.STDOUT, encoding='UTF-8').strip()

    assert 'Extremely small energy budget was submitted to Eco-CI API' in logs
    assert 'Measurement (CI_Measurement): energy_uj=1' in logs

def test_ci_measurement_add_force_ip():
    measurement = CI_Measurement(energy_uj=300,
                        repo='testRepo',
                        branch='testBranch',
                        cpu='testCPU',
                        cpu_util_avg=50,
                        commit_hash='1234asdf',
                        workflow='testWorkflow',
                        run_id='testRunID',
                        source='testSource',
                        label='testLabel',
                        duration_us=20000,
                        workflow_name='testWorkflowName',
                        lat="18.2972",
                        lon="77.2793",
                        city="Nine Mile",
                        carbon_intensity_g=100,
                        carbon_ug=1234567893453245,
                        ip='1.1.1.1')

    response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement.model_dump(), timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)

    query = 'SELECT * FROM ci_measurements WHERE run_id = %s' # we make * match to always test all columns. Even if we add some in the future. However they must be part of CI_Measurement
    data = DB().fetch_one(query, (measurement.run_id, ), fetch_mode='dict')

    ndata = {k: v for k, v in data.items() if k not in ['id', 'created_at', 'updated_at', 'workflow_id', 'workflow_name', 'user_id', 'filter_source']}

    ndata['ip'] = str(ndata['ip_address']) # model as a different key in DB
    del ndata['ip_address']

    assert CI_Measurement(workflow_name=measurement.workflow_name, workflow=measurement.workflow, **ndata).model_dump() == measurement.model_dump()
