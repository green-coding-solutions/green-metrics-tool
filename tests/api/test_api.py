import os
import pytest
import requests
import psycopg

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
    data = DB().fetch_one(query, (run_name, ), row_factory=psycopg.rows.dict_row)
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
    data = DB().fetch_one(query, (measurement.run_id, ), row_factory=psycopg.rows.dict_row)
    assert data is not None
    for key in measurement.model_dump().keys():
        if key == 'workflow':
            assert data['workflow_id'] == measurement.model_dump()[key], Tests.assertion_info(f"workflow_id: {data['workflow_id']}", measurement.model_dump()[key])
        else:
            assert data[key] == measurement.model_dump()[key], Tests.assertion_info(f"{key}: {data[key]}", measurement.model_dump()[key])


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
