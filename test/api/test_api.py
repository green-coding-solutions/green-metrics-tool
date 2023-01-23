#pylint: disable=no-name-in-module,wrong-import-position,import-error
import os
import sys
import requests

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../api")
sys.path.append(f"{current_dir}/../../lib")

import utils
from pydantic import BaseModel
from global_config import GlobalConfig

class Project(BaseModel):
    name: str
    url: str
    email: str
    branch: str


config = GlobalConfig(config_name='test-config.yml').config
API_URL = 'http://api.green-coding.local:9142'
PROJECT_NAME = 'test_' + utils.randomword(12)
PROJECT = Project(name=PROJECT_NAME, url='testURL', email='testEmail', branch='')


def test_post_project_add():
    response = requests.post(f"{API_URL}/v1/project/add", json=PROJECT.dict(), timeout=15)
    assert response.status_code == 200
    pid = utils.get_pid(PROJECT_NAME)
    assert pid is not None


def test_get_projects():
    response = requests.get(f"{API_URL}/v1/projects", timeout=15)
    res_json = response.json()
    pid = utils.get_pid(PROJECT_NAME)
    assert response.status_code == 200
    assert res_json['data'][0][0] == pid
