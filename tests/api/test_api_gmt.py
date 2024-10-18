import os
import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib import utils
from lib.global_config import GlobalConfig

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

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

def test_get_runs():
    run_name = 'test_' + utils.randomword(12)
    uri = os.path.abspath(os.path.join(
            CURRENT_DIR, 'stress-application/'))
    pid = DB().fetch_one("INSERT INTO runs (name,uri,branch,filename,email,created_at) \
                    VALUES \
                    (%s,%s,'testing','testing', 'testing', NOW()) RETURNING id;", params=(run_name, uri))[0]

    response = requests.get(f"{API_URL}/v1/runs?repo=&filename=", timeout=15)
    res_json = response.json()
    assert response.status_code == 200
    assert res_json['data'][0][0] == str(pid)
