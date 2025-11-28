import json
import os
import requests

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

# This comes from the hog tests under
# https://github.com/green-coding-solutions/hog/tree/main/tests
hog_string = '''eJyNlV1v2jAUhv9KxXXx/P2xu67tRbWtnQTaLqYpMo4Br4kdOWG0q/rfd8y4KBCkGoVETvL4nOPzvnmZtNatQ/TVZhPqyceLCbeKOUf5FBtlpoQs8XQhnZwqT5UlRKua1ZPLi8kQWt8Ptu3gJaI41UxwjmGUe6mrupyc73vfw/2fL5NoW1/wLrWoDS6nPi0H9H12nWpfcD76vHquQttZNxQkETDruk1Zp2oLhTKNiNKUS0IxVhqz18uLQ7LtusYju6lDQi5lv7uqx/iSHeMlQ0YwjKkxmnGpMT/Ad2nrc+uHHFw/BuTkGMgYYowa+HEqqeBHQL9B/sk3CxvRbLDDKJSdQCVFXFHFiJGCCy3PlaD8951vmtHiqmMskQaVDceClpM8ijXMIXf6PpRUiDMhoJZEE80xOSA9+hx9U7lkmzCEFEeZJ1tPCEFSasgbGw4D0zN5/wixTtuZz398HkXzk13CFBmmDIU9N4xxrE7Q9cY9lmOVEKgl9WiR07YfX+CkrShGlEIbEGyIlqCPw9Bvbq9uqvnV7POsun64+nI3v3u4fxeXYcS41gZrQihXckQNdXJQ7v1pDEqPocIgUIChShOlMNXkTJndOqc4LqwTJkNECG5AsdC1EizinGxdisuwGoWeyIAgxYVkEnqM6uIFZyNddtkv+xo9dQ7ZlY/Du/gCcYEZE0YLaA08gu+7NITlM3JNeC+UEiSkNlwwQ4U0pRV+7Z30b4o78vXt/MP17WxeeKsc6irEwcc+DM8gmVWB7gwWAliAadfVfs32d3Egs6/94awsalodzdIiWwu2/3YSj/WdKLPrbdWCUTclxK/WfUrp8VtORF+yXeKN7XoIJu52BlNwD0qkLKmtwTdsAx8D+BRs8i7F+9SGaP/7UrtIdYA3nc2LFKuSIEYYaxAk1kqB0RVUKWTqfLbFMID25mmCmDwYyk+xeP0H10gRpw=='''


def test_hogDB_add():
    hog_data_obj  = [{
        "time": 1710668240000,
        "data": hog_string,
        "settings": json.dumps({"powermetrics": 5000, "upload_delta": 3, "upload_data": True, "resolve_coalitions": ["com.googlecode.iterm2", "com.apple.terminal", "com.vix.cron"], "client_version": "0.5"}),
        "machine_uuid": "371ee758-d4e6-11ee-a082-7e27a1187d3d",
        "row_id": 1,
    }]

    response = requests.post(f"{API_URL}/v2/hog/add", json=hog_data_obj, timeout=15)
    assert response.status_code == 204, response.text

    results = {
        'combined_energy_mj': 492,
        'cpu_energy_mj': 465,
        'gpu_energy_mj': 27,
        'ane_energy_mj': 0,
        'energy_impact': 350,
        'operational_carbon_g': 1.3666666666666667e-05,
        'embodied_carbon_g': 0.008937087772704211,
    }

    q = 'SELECT * FROM hog_simplified_measurements'#, 'SELECT * FROM hog_top_processes']

    data = DB().fetch_one(q, fetch_mode='dict')

    assert(data['combined_energy_uj'] == results['combined_energy_mj'] * 1_000 and \
        data['cpu_energy_uj'] == results['cpu_energy_mj'] * 1_000 and \
        data['gpu_energy_uj'] == results['gpu_energy_mj'] * 1_000 and \
        data['ane_energy_uj'] == results['ane_energy_mj'] * 1_000 and \
        data['energy_impact'] == results['energy_impact'] and \
        data['grid_intensity_cog'] == 100 and \
        data['embodied_carbon_ug'] == results['embodied_carbon_g'] * 1_000_000 and \
        data['operational_carbon_ug'] == results['operational_carbon_g'] * 1_000_000)

    response = requests.get(f"{API_URL}/v2/hog/top_processes", timeout=15, headers={'X-Authentication': 'DEFAULT'})
    assert response.status_code == 200, Tests.assertion_info('success', response.text)

    r = '{"success":true,"process_data":[["com.microsoft.VSCode",115],["com.apple.audio.coreaudiod",63],["powermetrics",41],["eu.exelban.Stats",31],["com.apple.applespell",17],["iTerm2",17],["kernel_coalition",15],["com.apple.WindowServer",14],["DEAD_TASKS_COALITION",3],["com.duckduckgo.macos.browser",3]],"machine_count":1}'
    assert response.text == r

    response = requests.get(f"{API_URL}/v2/hog/details", timeout=15, headers={'X-Authentication': 'DEFAULT'})
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    obj = json.loads(response.text)

    assert obj['total_combined_energy_uj'] == results['combined_energy_mj'] * 1_000
    assert obj['total_cpu_energy_uj'] == results['cpu_energy_mj'] * 1_000
    assert obj['total_gpu_energy_uj'] == results['gpu_energy_mj'] * 1_000
    assert obj['total_ane_energy_uj'] == results['ane_energy_mj'] * 1_000
    assert obj['total_energy_impact'] == results['energy_impact']
    assert obj['total_operational_carbon_ug'] == results['operational_carbon_g'] * 1_000_000
    assert obj['total_embodied_carbon_ug'] == results['embodied_carbon_g'] * 1_000_000
