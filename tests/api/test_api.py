import json
import os
import time
from uuid import UUID
import pytest
import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib import utils
from lib.global_config import GlobalConfig
from tools.machine import Machine
from tests import test_functions as Tests

config = GlobalConfig(config_name='test-config.yml').config
API_URL = config['cluster']['api_url']

from api.main import Software
from api.main import CI_Measurement

import hog_data

@pytest.fixture(autouse=True, name="register_machine")
def register_machine_fixture():
    machine = Machine(machine_id=1, description='test-machine')
    machine.register()

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

def test_ci_measurement_add():
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
            SELECT * FROM ci_measurements WHERE run_id = %s
            """
    data = DB().fetch_one(query, (measurement.run_id, ), fetch_mode='dict')
    assert data is not None
    for key in measurement.model_dump():
        if key == 'workflow':
            assert data['workflow_id'] == measurement.model_dump()[key], Tests.assertion_info(f"workflow_id: {data['workflow_id']}", measurement.model_dump()[key])
        elif key in ['cb_company_uuid', 'cb_project_uuid', 'cb_machine_uuid']:
            pass
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
