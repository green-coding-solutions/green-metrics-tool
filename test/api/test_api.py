import os
import sys
import pytest
import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../api")
sys.path.append(f"{current_dir}/../../lib")

#pylint: disable=import-error
from db import DB
import utils
from pydantic import BaseModel
from global_config import GlobalConfig
import test_functions as Tests

class Run(BaseModel):
    name: str
    url: str
    email: str
    branch: str
    filename: str
    machine_id: int


config = GlobalConfig(config_name='test-config.yml').config
API_URL = config['cluster']['api_url']
RUN_NAME = 'test_' + utils.randomword(12)
run = Run(name=RUN_NAME, url='testURL', email='testEmail', branch='', filename='', machine_id=0)

@pytest.fixture()
def cleanup_runs():
    yield
    DB().query('DELETE FROM runs')

def test_post_run_add(cleanup_runs):
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)
    pid = utils.get_run_data(RUN_NAME)['id']
    assert pid is not None

def test_get_runs(cleanup_runs):
    NEW_RUN_NAME = 'test_' + utils.randomword(12)
    uri = os.path.abspath(os.path.join(
            current_dir, 'stress-application/'))
    pid = DB().fetch_one('INSERT INTO "runs" ("name","uri","email","last_run","created_at") \
                    VALUES \
                    (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(NEW_RUN_NAME, uri))[0]
    response = requests.get(f"{API_URL}/v1/runs?repo=&filename=", timeout=15)
    res_json = response.json()
    assert response.status_code == 200
    assert res_json['data'][0][0] == str(pid)
