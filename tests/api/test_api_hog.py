import base64
import json
import os
import zlib
import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests
import time

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

# This comes from the hog tests under
# https://github.com/green-coding-solutions/hog/tree/main/tests
hog_string = json.loads('''{"machine_uuid": "4a73cc24-0979-11f0-b6c6-7e27a1187d3d", "timestamp": ''' + str(int(time.time() * 1000)) + ''', "top_processes": [{"name": "com.microsoft.VSCode", "energy_impact": 115, "cputime_ms": 238.17824612007803}, {"name": "com.apple.audio.coreaudiod", "energy_impact": 63, "cputime_ms": 63.953002998346804}, {"name": "powermetrics", "energy_impact": 41, "cputime_ms": 33.332929242625404}, {"name": "eu.exelban.Stats", "energy_impact": 31, "cputime_ms": 62.4727319654586}, {"name": "com.apple.applespell", "energy_impact": 17, "cputime_ms": 169.09790520979604}, {"name": "iTerm2", "energy_impact": 17, "cputime_ms": 67.43559531818401}, {"name": "kernel_coalition", "energy_impact": 15, "cputime_ms": 111.66827309444402}, {"name": "com.apple.WindowServer", "energy_impact": 14, "cputime_ms": 302.93792346933407}, {"name": "com.duckduckgo.macos.browser", "energy_impact": 3, "cputime_ms": 20.223291091860002}, {"name": "DEAD_TASKS_COALITION", "energy_impact": 3, "cputime_ms": 30.348890811247603}, {"name": "com.docker.docker", "energy_impact": 2, "cputime_ms": 59.30092781770281}, {"name": "com.apple.chronod", "energy_impact": 2, "cputime_ms": 3.1554900773164003}, {"name": "com.apple.configd", "energy_impact": 1, "cputime_ms": 1.7456363182807801}, {"name": "com.apple.cfprefsd.xpc.agent", "energy_impact": 1, "cputime_ms": 5.450335985792001}, {"name": "com.spotify.client", "energy_impact": 1, "cputime_ms": 21.568945392569002}], "timezone": "CET/CEST", "grid_intensity_cog": 100, "combined_energy_mj": 492, "cpu_energy_mj": 465, "gpu_energy_mj": 27, "ane_energy_mj": 0, "energy_impact": 350, "hw_model": "MacBookPro18,3", "elapsed_ns": 1026042166, "thermal_pressure": "Nominal", "embodied_carbon_g": 0.008937087772704211, "operational_carbon_g": 1.3666666666666667e-05}''')

compressed_data = zlib.compress(str(json.dumps(hog_string)).encode())
compressed_data_str = base64.b64encode(compressed_data).decode()


def test_hogDB_add():
    hog_data_obj  = [{
        "time": int(time.time() * 1000),
        "data": compressed_data_str,
        "settings": json.dumps({"powermetrics": 5000, "upload_delta": 3, "upload_data": True, "resolve_coalitions": ["com.googlecode.iterm2", "com.apple.terminal", "com.vix.cron"], "client_version": "0.5"}),
        "machine_uuid": "371ee758-d4e6-11ee-a082-7e27a1187d3d",
        "row_id": 1,
    }]

    response = requests.post(f"{API_URL}/v2/hog/add", json=hog_data_obj, timeout=15, headers={'X-Authentication': 'DEFAULT'})
    assert response.status_code == 202, response.text

    q = 'SELECT * FROM hog_simplified_measurements'#, 'SELECT * FROM hog_top_processes']

    data = DB().fetch_one(q, fetch_mode='dict')
    assert(data['combined_energy_uj'] == hog_string['combined_energy_mj'] * 1_000 and \
        data['cpu_energy_uj'] == hog_string['cpu_energy_mj'] * 1_000 and \
        data['gpu_energy_uj'] == hog_string['gpu_energy_mj'] * 1_000 and \
        data['ane_energy_uj'] == hog_string['ane_energy_mj'] * 1_000 and \
        data['energy_impact'] == hog_string['energy_impact'] and \
        data['grid_intensity_cog'] == 100 and \
        data['embodied_carbon_ug'] == hog_string['embodied_carbon_g'] * 1_000_000 and \
        data['operational_carbon_ug'] == hog_string['operational_carbon_g'] * 1_000_000)

    response = requests.get(f"{API_URL}/v2/hog/top_processes", timeout=15, headers={'X-Authentication': 'DEFAULT'})
    assert response.status_code == 200, Tests.assertion_info('success', response.text)

    r = '{"success":true,"process_data":[["com.microsoft.VSCode",115],["com.apple.audio.coreaudiod",63],["powermetrics",41],["eu.exelban.Stats",31],["com.apple.applespell",17],["iTerm2",17],["kernel_coalition",15],["com.apple.WindowServer",14],["DEAD_TASKS_COALITION",3],["com.duckduckgo.macos.browser",3]],"machine_count":1}'
    assert response.text == r

    response = requests.get(f"{API_URL}/v2/hog/details", timeout=15, headers={'X-Authentication': 'DEFAULT'})
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    obj = json.loads(response.text)
    assert obj['total_combined_energy_uj'] == hog_string['combined_energy_mj'] * 1_000
    assert obj['total_cpu_energy_uj'] == hog_string['cpu_energy_mj'] * 1_000
    assert obj['total_gpu_energy_uj'] == hog_string['gpu_energy_mj'] * 1_000
    assert obj['total_ane_energy_uj'] == hog_string['ane_energy_mj'] * 1_000
    assert obj['total_energy_impact'] == hog_string['energy_impact']
    assert obj['total_operational_carbon_ug'] == hog_string['operational_carbon_g'] * 1_000_000
    assert obj['total_embodied_carbon_ug'] == hog_string['embodied_carbon_g'] * 1_000_000
