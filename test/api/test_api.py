import os
import sys
import pytest
import requests
import psycopg

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../api")
sys.path.append(f"{current_dir}/../../lib")
sys.path.append(f"{current_dir}/../../tools")

#pylint: disable=import-error
from db import DB
from machine import Machine
import utils
from global_config import GlobalConfig
import test_functions as Tests

config = GlobalConfig(config_name='test-config.yml').config
API_URL = config['cluster']['api_url']

# import software class from api.py
from api import Software

@pytest.fixture(autouse=True, scope="module", name="register_machine")
def register_machine_fixture():
    machine = Machine(machine_id=0, description='test-machine')
    machine.register()

@pytest.fixture(autouse=True, name='cleanup_runs')
def cleanup_runs_fixture():
    yield
    DB().query('DELETE FROM runs')

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
    run = Software(name=run_name, url='testURL', email='testEmail', branch='', filename='', machine_id=0, schedule_mode='one-off')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    job_id = get_job_id(run_name)
    assert job_id is not None

def todo_test_get_runs():
    run_name = 'test_' + utils.randomword(12)
    uri = os.path.abspath(os.path.join(
            current_dir, 'stress-application/'))
    pid = DB().fetch_one('INSERT INTO "runs" ("name","uri","email","last_run","created_at") \
                    VALUES \
                    (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(run_name, uri))[0]

    response = requests.get(f"{API_URL}/v1/runs?repo=&filename=", timeout=15)
    res_json = response.json()
    assert response.status_code == 200
    assert res_json['data'][0][0] == str(pid)
