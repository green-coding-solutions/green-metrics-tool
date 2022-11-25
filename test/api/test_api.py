import requests
import os
import sys

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

config = GlobalConfig(config_name="test-config.yml").config
API_URL="http://api.green-coding.local:8000"
project_name = "test_" + utils.randomword(12)
p = Project(name=project_name, url="testURL", email="testEmail")
pid = None

def test_post_project_add():
    response = requests.post(f"{API_URL}/v1/project/add", json = p.dict())
    r = response.json()
    assert response.status_code == 200
    pid = get_pid(project_name)
    assert pid != None

def test_get_projects():
    response = requests.get(f"{API_URL}/v1/projects")
    r = response.json()
    pid = get_pid(project_name)
    assert response.status_code == 200
    assert r["data"][0][0] == pid

def get_pid(project_name):
    query = """
            SELECT
                id
            FROM
                projects
            WHERE name = %s
            """
    data = DB().fetch_one(query, (project_name, ))
    if(data is None or data == []):
        return None
    else:
        return data[0]