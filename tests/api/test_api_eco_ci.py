import os
import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

from api.main import CI_Measurement

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

def test_ci_measurement_add_default_user():
    measurement = CI_Measurement(energy_value=123,
                        energy_unit='mJ',
                        repo='testRepo',
                        branch='testBranch',
                        cpu='testCPU',
                        cpu_util_avg=50,
                        commit_hash='1234asdf',
                        workflow='testWorkflow',
                        run_id='testRunID',
                        source='testSource',
                        label='testLabel',
                        duration=20,
                        workflow_name='testWorkflowName')
    response = requests.post(f"{API_URL}/v1/ci/measurement/add", json=measurement.model_dump(), timeout=15)
    assert response.status_code == 201, Tests.assertion_info('success', response.text)
    query = """
            SELECT * FROM ci_measurements WHERE run_id = %s -- we make * match to always test all columns. Even if we add some in the future
            """
    data = DB().fetch_one(query, (measurement.run_id, ), fetch_mode='dict')

    assert data is not None
    for key in data:
        if key == 'workflow_id':
            assert data[key] == measurement.model_dump()['workflow'], Tests.assertion_info(f"workflow_id: {data[key]}", measurement.model_dump()['workflow'])
        elif key in ['id', 'cb_company_uuid', 'cb_project_uuid', 'cb_machine_uuid', 'created_at', 'updated_at']:
            pass
        elif key == 'user_id':
            assert data[key] == 1, Tests.assertion_info(1, f"{key}: {data[key]}")
        else:
            assert data[key] == measurement.model_dump()[key], Tests.assertion_info(f"{key}: {data[key]}", measurement.model_dump()[key])

def test_ci_measurement_add_different_user():
    measurement = CI_Measurement(energy_value=123,
                        energy_unit='mJ',
                        repo='testRepo',
                        branch='testBranch',
                        cpu='testCPU',
                        cpu_util_avg=50,
                        commit_hash='1234asdf',
                        workflow='testWorkflow',
                        run_id='testRunID',
                        source='testSource',
                        label='testLabel',
                        duration=20,
                        workflow_name='testWorkflowName')

    Tests.insert_user(2, 'PYTEST')

    response = requests.post(f"{API_URL}/v1/ci/measurement/add", json=measurement.model_dump(), timeout=15, headers={'X-Authentication': 'PYTEST'})
    assert response.status_code == 201, Tests.assertion_info('success', response.text)
    query = """
            SELECT * FROM ci_measurements WHERE run_id = %s -- we make * match to always test all columns. Even if we add some in the future
            """
    data = DB().fetch_one(query, (measurement.run_id, ), fetch_mode='dict')

    assert data is not None
    for key in data:
        if key == 'workflow_id':
            assert data[key] == measurement.model_dump()['workflow'], Tests.assertion_info(f"workflow_id: {data[key]}", measurement.model_dump()['workflow'])
        elif key in ['id', 'cb_company_uuid', 'cb_project_uuid', 'cb_machine_uuid', 'created_at', 'updated_at']:
            pass
        elif key == 'user_id':
            assert data[key] == 2, Tests.assertion_info(3, f"{key}: {data[key]}")
        else:
            assert data[key] == measurement.model_dump()[key], Tests.assertion_info(f"{key}: {data[key]}", measurement.model_dump()[key])



def test_ci_measurement_add_co2():
    measurement = CI_Measurement(energy_value=123,
                        energy_unit='mJ',
                        repo='testRepo',
                        branch='testBranch',
                        cpu='testCPU',
                        cpu_util_avg=50,
                        commit_hash='1234asdf',
                        workflow='testWorkflow',
                        run_id='testRunID',
                        source='testSource',
                        label='testLabel',
                        duration=20,
                        workflow_name='testWorkflowName',
                        lat="18.2972",
                        lon="77.2793",
                        city="Nine Mile",
                        co2i="100",
                        co2eq="0.1234567893453245"
                        )

    response = requests.post(f"{API_URL}/v1/ci/measurement/add", json=measurement.model_dump(), timeout=15)
    assert response.status_code == 201, Tests.assertion_info('success', response.text)
    query = """
            SELECT * FROM ci_measurements WHERE run_id = %s
            """
    data = DB().fetch_one(query, (measurement.run_id, ), fetch_mode='dict')
    ndata = {k: v for k, v in data.items() if k not in ['id', 'created_at', 'updated_at', 'workflow_id', 'workflow_name']}
    assert CI_Measurement(workflow_name='testWorkflowName', workflow='testWorkflow', **ndata).model_dump() == measurement.model_dump()
