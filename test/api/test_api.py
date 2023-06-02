#pylint: disable=no-name-in-module,wrong-import-position,import-error, redefined-outer-name, unused-argument
import os
import sys
import pytest
import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../api")
sys.path.append(f"{current_dir}/../../lib")

from db import DB
import utils
from test_functions import assertion_info
from pydantic import BaseModel
from global_config import GlobalConfig
import test_functions as Tests

class Project(BaseModel):
    name: str
    url: str
    email: str
    branch: str
    machine_id:int


config = GlobalConfig(config_name='test-config.yml').config
API_URL = config['cluster']['api_url']
PROJECT_NAME = 'test_' + utils.randomword(12)
PROJECT = Project(name=PROJECT_NAME, url='testURL', email='testEmail', branch='', machine_id=0)

@pytest.fixture()
def cleanup_projects():
    yield
    DB().query('DELETE FROM projects')

def test_post_project_add(cleanup_projects):
    response = requests.post(f"{API_URL}/v1/project/add", json=PROJECT.dict(), timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)
    pid = utils.get_project_data(PROJECT_NAME)['id']
    assert pid is not None


def test_get_projects(cleanup_projects):
    project_name = 'test_' + utils.randomword(12)
    uri = os.path.abspath(os.path.join(
            current_dir, 'stress-application/'))
    pid = DB().fetch_one('INSERT INTO "projects" ("name","uri","email","last_run","created_at") \
                    VALUES \
                    (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(project_name, uri))[0]
    response = requests.get(f"{API_URL}/v1/projects", timeout=15)
    res_json = response.json()
    assert response.status_code == 200
    assert res_json['data'][0][0] == str(pid)
