import json
import os
import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib.global_config import GlobalConfig

config = GlobalConfig(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml").config
API_URL = config['cluster']['api_url']

import hog_data


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
