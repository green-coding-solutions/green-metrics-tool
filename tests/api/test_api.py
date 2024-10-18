import json
import os
import time
from uuid import UUID
import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.user import User
from lib.db import DB
from lib import utils
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

from api.main import Software
from api.main import CI_Measurement

import hog_data

def get_job_id(run_name):
    query = """
            SELECT
                *
            FROM
                jobs
            WHERE name = %s
            """
    data = DB().fetch_one(query, (run_name, ), fetch_mode='dict')
    if data is None or data == []:
        return None
    return data['id']

def test_post_run_add():
    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, url='testURL', email='testEmail', branch='', filename='', machine_id=1, schedule_mode='one-off')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    job_id = get_job_id(run_name)
    assert job_id is not None

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

    DB().query("""
        INSERT INTO "public"."users"("id", "name","token","capabilities","created_at","updated_at")
        VALUES
        (2, E'PYTEST',E'ee8e09e43bceff39c9410f11a2392a3f6b868557240002b72dbdd22a2f792eef',E'{"api":{"quotas":{},"routes":["/v1/carbondb/add","/v1/ci/measurement/add","/v1/software/add","/v1/hog/add","/v1/authentication/data"]},"data":{"runs":{"retention":2678400},"hog_tasks":{"retention":2678400},"measurements":{"retention":2678400},"hog_coalitions":{"retention":2678400},"ci_measurements":{"retention":2678400},"hog_measurements":{"retention":2678400}},"jobs":{"schedule_modes":["one-off","daily","weekly","commit","variance"]},"machines":[1],"measurement":{"quotas":{},"settings":{"total-duration":86400,"flow-process-duration":86400}},"optimizations":["container_memory_utilization","container_cpu_utilization","message_optimization","container_build_time","container_boot_time","container_image_size"]}',E'2024-08-22 11:28:24.937262+00',NULL);
    """)

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


def test_carbonDB_measurement_add():
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
                        cb_machine_uuid='fa4e21ee-c733-465c-bc4a-ce5c02eed63b')

    exp_data = {'type': 'machine.ci',
                'company': None,
                'machine': UUID('fa4e21ee-c733-465c-bc4a-ce5c02eed63b'),
                'project': None,
                'tags': ['testLabel', 'testRepo', 'testBranch', 'testWorkflow'],
                'energy_value': 0.123,
                'co2_value': 3.4166693999999996e-05,
                'carbon_intensity': 1000.0,
                'latitude': 52.53721666833642,
                'longitude': 13.424863870661927
                }

    response = requests.post(f"{API_URL}/v1/ci/measurement/add", json=measurement.model_dump(), timeout=15)
    assert response.status_code == 201, Tests.assertion_info('success', response.text)
    query = """
            SELECT * FROM carbondb_energy_data
            """
    data = DB().fetch_one(query, fetch_mode='dict')
    assert data is not None or data != []
    assert exp_data == {key: data[key] for key in exp_data if key in data}, "The specified keys do not have the same values in both dictionaries."


def todo_test_get_runs():
    run_name = 'test_' + utils.randomword(12)
    uri = os.path.abspath(os.path.join(
            CURRENT_DIR, 'stress-application/'))
    pid = DB().fetch_one('INSERT INTO "runs" ("name","uri","email","last_run","created_at") \
                    VALUES \
                    (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(run_name, uri))[0]

    response = requests.get(f"{API_URL}/v1/runs?repo=&filename=", timeout=15)
    res_json = response.json()
    assert response.status_code == 200
    assert res_json['data'][0][0] == str(pid)



def test_hogDB_add():
    hog_data_obj  = [
    {
        "time": 1710668240000,
        "data": hog_data.hog_string,
        "settings": json.dumps({"powermetrics": 5000, "upload_delta": 3, "upload_data": True, "resolve_coalitions": ["com.googlecode.iterm2", "com.apple.terminal", "com.vix.cron"], "client_version": "0.5"}),
        "machine_uuid": "371ee758-d4e6-11ee-a082-7e27a1187d3d",
        "row_id": 51},
    ]

    response = requests.post(f"{API_URL}/v1/hog/add", json=hog_data_obj, timeout=15)
    assert response.status_code == 204

    queries = ['SELECT * FROM hog_tasks', 'SELECT * FROM hog_coalitions', 'SELECT * FROM hog_measurements']
    for q in queries:
        data = DB().fetch_one(q, fetch_mode='dict')
        assert data is not None or data != []


def test_carbonDB_add():
    energydata = {
        'type': 'machine.ci',
        'energy_value': '1',
        'time_stamp': str(int(time.time() * 1e6)),
        'company': '',
        'project': '',
        'machine': 'f6d93b14-31c3-4565-9833-675371c67f2f',
        'tags': "x,y"
    }

    exp_data = {
        'type': 'machine.ci',
        'company': None,
        'machine': UUID('f6d93b14-31c3-4565-9833-675371c67f2f'),
        'project': None,
        'tags': ['x', 'y'],
        'time_stamp': int(energydata['time_stamp']),
        'energy_value': 1.0,
        'co2_value': 0.000277778,
        'carbon_intensity': 1000.0,
        'latitude': 52.53721666833642,
        'longitude': 13.424863870661927
        }

    response = requests.post(f"{API_URL}/v1/carbondb/add", json=[energydata], timeout=15)
    assert response.status_code == 204

    data = DB().fetch_one('SELECT * FROM carbondb_energy_data', fetch_mode='dict')
    assert data is not None or data != []
    assert exp_data == {key: data[key] for key in exp_data if key in data}, "The specified keys do not have the same values in both dictionaries."

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
    assert response.text == '{"success":true,"data":{"_id":1,"_name":"DEFAULT","_capabilities":{"api":{"quotas":{},"routes":["/v1/carbondb/add","/v1/ci/measurement/add","/v1/software/add","/v1/hog/add","/v1/authentication/data"]},"data":{"runs":{"retention":2678400},"hog_tasks":{"retention":2678400},"measurements":{"retention":2678400},"hog_coalitions":{"retention":2678400},"ci_measurements":{"retention":2678400},"hog_measurements":{"retention":2678400}},"jobs":{"schedule_modes":["one-off","daily","weekly","commit","variance"]},"machines":[1],"measurement":{"quotas":{},"settings":{"total-duration":86400,"flow-process-duration":86400}},"optimizations":["container_memory_utilization","container_cpu_utilization","message_optimization","container_build_time","container_boot_time","container_image_size"]}}}'

def test_api_quota_exhausted():
    user = User(1)
    user._capabilities['api']['quotas'] = {'/v1/authentication/data': 0}
    user.update()

    response = requests.get(f"{API_URL}/v1/authentication/data", timeout=15)
    assert response.status_code == 401
    assert response.text == '{"success":false,"err":"Quota exceeded"}'
