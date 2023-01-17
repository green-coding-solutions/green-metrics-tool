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
from db import DB

class Project(BaseModel):
    name: str
    url: str
    email: str


config = GlobalConfig(config_name='test-config.yml').config
API_URL = 'http://api.green-coding.local:9142'
PROJECT_NAME = 'test_' + utils.randomword(12)
PROJECT = Project(name=PROJECT_NAME, url='testURL', email='testEmail')


def test_post_project_add():
    response = requests.post(f"{API_URL}/v1/project/add", json=PROJECT.dict(), timeout=15)
    assert response.status_code == 200
    pid = get_pid(PROJECT_NAME)
    assert pid is not None


def test_get_projects():
    response = requests.get(f"{API_URL}/v1/projects", timeout=15)
    res_json = response.json()
    pid = get_pid(PROJECT_NAME)
    assert response.status_code == 200
    assert res_json['data'][0][0] == pid


def get_pid(project_name):
    query = """
            SELECT
                id
            FROM
                projects
            WHERE name = %s
            """
    data = DB().fetch_one(query, (project_name, ))
    if (data is None or data == []):
        return None

    return data[0]
