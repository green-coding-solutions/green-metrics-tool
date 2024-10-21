import os
import requests
import ipaddress
import time
import math
import json

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.user import User
from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

ENERGY_DATA = {
    'type': 'machine.ci',
    'energy_uj': 1,
    'time': int(time.time() * 1e6),
    'project': 'my-project',
    'machine': 'my-machine',
    'tags': ['mystery', 'cool']
}

def test_carbondb_add_unauthenticated():
    user = User(1)
    user._capabilities['api']['routes'] = []
    user.update()

    response = requests.post(f"{API_URL}/v2/carbondb/add", json=ENERGY_DATA, timeout=15)
    assert response.status_code == 401, Tests.assertion_info('success', response.text)

def test_carbondb_add():

    exp_data = ENERGY_DATA.copy()
    del exp_data['energy_uj']
    exp_data['energy_kwh'] = 2.7777777777777774e-13 # 1 uJ
    exp_data['carbon_kg'] = 2.7777777777777777e-13 # 1e-6J / (3600 * 1000) = kwH = 2.7777777777777774e-13 => * 1000 => 2.77e-10 g = 2.77e-13 kg
    exp_data['carbon_intensity_g'] = 1000.0 # because we have no electricitymaps token set
    exp_data['latitude'] = 52.53721666833642
    exp_data['longitude'] = 13.42486387066192

    response = requests.post(f"{API_URL}/v2/carbondb/add", json=ENERGY_DATA, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = DB().fetch_one('SELECT * FROM carbondb_data_raw', fetch_mode='dict')
    assert data is not None or data != []
    assert_expected_data(exp_data, data)

def test_carbondb_add_force_ip():
    energydata_modified = ENERGY_DATA.copy()
    energydata_modified['ip'] = '1.1.1.1'


    exp_data = energydata_modified.copy()
    del exp_data['energy_uj']
    exp_data['ip_address'] = ipaddress.IPv4Address('1.1.1.1')
    exp_data['latitude'] = -27.4766 # Hmm, this can be flaky! But also we want to test the IP API
    exp_data['longitude'] = 153.0166 # Hmm, this can be flaky! But also we want to test the IP API

    response = requests.post(f"{API_URL}/v2/carbondb/add", json=energydata_modified, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = DB().fetch_one('SELECT * FROM carbondb_data_raw', fetch_mode='dict')
    assert data is not None or data != []
    assert_expected_data(exp_data, data)


def test_carbondb_add_force_carbon_intensity():

    energydata_modified = ENERGY_DATA.copy()
    energydata_modified['carbon_intensity_g'] = 200

    exp_data = energydata_modified.copy()
    del exp_data['energy_uj']
    exp_data['carbon_intensity_g'] = 200
    exp_data['carbon_kg'] = 5.555555555555555e-14

    response = requests.post(f"{API_URL}/v2/carbondb/add", json=energydata_modified, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = DB().fetch_one('SELECT * FROM carbondb_data_raw', fetch_mode='dict')
    assert data is not None or data != []
    assert_expected_data(exp_data, data)


def test_carbondb_missing_values():
    energydata_crap = {
    }
    response = requests.post(f"{API_URL}/v2/carbondb/add", json=energydata_crap, timeout=15)
    assert response.status_code == 422, Tests.assertion_info('success', response.text)
    assert response.text == '{"success":false,"err":[{"type":"missing","loc":["body","project"],"msg":"Field required","input":{}},{"type":"missing","loc":["body","machine"],"msg":"Field required","input":{}},{"type":"missing","loc":["body","type"],"msg":"Field required","input":{}},{"type":"missing","loc":["body","time"],"msg":"Field required","input":{}},{"type":"missing","loc":["body","energy_uj"],"msg":"Field required","input":{}}],"body":{}}'

def test_carbondb_non_int():
    energydata_broken = {
        'type': 123,
        'energy_uj': 'no-int',
        'time': 'no-time',
        'project': 678,
        'machine': 9,
    }
    response = requests.post(f"{API_URL}/v2/carbondb/add", json=energydata_broken, timeout=15)
    assert response.status_code == 422, Tests.assertion_info('success', response.text)
    assert response.text == '{"success":false,"err":[{"type":"string_type","loc":["body","project"],"msg":"Input should be a valid string","input":678},{"type":"string_type","loc":["body","machine"],"msg":"Input should be a valid string","input":9},{"type":"string_type","loc":["body","type"],"msg":"Input should be a valid string","input":123},{"type":"int_parsing","loc":["body","time"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"no-time"},{"type":"int_parsing","loc":["body","energy_uj"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"no-int"}],"body":{"type":123,"energy_uj":"no-int","time":"no-time","project":678,"machine":9}}'

def test_carbondb_superflous():
    energydata_superflous = ENERGY_DATA.copy()
    energydata_superflous['no-need'] = 1
    response = requests.post(f"{API_URL}/v2/carbondb/add", json=energydata_superflous, timeout=15)
    assert response.status_code == 422, Tests.assertion_info('success', response.text)
    assert json.loads(response.text)['err'][0]['type'] == 'extra_forbidden'
    assert json.loads(response.text)['err'][0]['loc'] == ['body','no-need']

def test_carbondb_empty_filters():
    energydata_modified = ENERGY_DATA.copy()
    energydata_modified['type'] = ''
    energydata_modified['project'] = ''
    energydata_modified['machine'] = ''
    energydata_modified['tags'] = ['','']

    response = requests.post(f"{API_URL}/v2/carbondb/add", json=energydata_modified, timeout=15)
    assert response.status_code == 422, Tests.assertion_info('success', response.text)

    assert response.text.startswith('''{"success":false,"err":[{"type":"value_error","loc":["body","tags"],"msg":"Value error, The list contains empty elements.","input":["",""],"ctx":{"error":{}}},{"type":"value_error","loc":["body","project"],"msg":"Value error, Value is empty","input":"","ctx":{"error":{}}},{"type":"value_error","loc":["body","machine"],"msg":"Value error, Value is empty","input":"","ctx":{"error":{}}},{"type":"value_error","loc":["body","type"],"msg":"Value error, Value is empty","input":"","ctx":{"error":{}}}]''')


def test_carbondb_weird_tags():
    energydata_modified = ENERGY_DATA.copy()
    energydata_modified['tags'] = ['öla', '<asd>']

    response = requests.post(f"{API_URL}/v2/carbondb/add", json=energydata_modified, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('success', response.text)

    data = DB().fetch_one('SELECT tags FROM carbondb_data_raw', fetch_mode='dict')
    assert data['tags'] == energydata_modified['tags']


def test_carbondb_no_filters():

    response = requests.get(f"{API_URL}/v2/carbondb/filters", timeout=15, headers={'X-Authentication': 'DEFAULT'})
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert response.text == '{"success":true,"data":{"types":null,"tags":null,"machines":null,"projects":null,"sources":null}}'



def test_carbondb_alternative_user_and_data():

    Tests.import_demo_data()
    response = requests.get(f"{API_URL}/v2/carbondb/filters", timeout=15, headers={'X-Authentication': 'DEFAULT'})
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert response.text == '{"success":true,"data":{"types":{"1":"machine.test","2":"generator.solar","3":"asdasd","4":"machine.ci","5":"machine.server"},"tags":{"111":"Environment setup (OS ubuntu-24.04","115":"green-coding.ai","118":"green-coding-solutions/ci-carbon-testing","119":"Measurement #1","120":"Environment setup (Python","135":"metrics.green-coding.io"},"machines":{"1":"GCS HQ Solar Panel","5":"metrics.green-coding.io","11":"green-coding.ai","20":"metrics.green-coding.io-alt","22":"ubuntu-latest"},"projects":{"1":"Projekt #1","2":"Projekt #2","3":"Projekt #3","4":"Projekt #4"},"sources":{"1":"UNDEFINED"}}}'

    Tests.insert_user(345, 'ALTERNATIVE-USER-CARBONDB')
    response = requests.get(f"{API_URL}/v2/carbondb/filters", timeout=15, headers={'X-Authentication': 'ALTERNATIVE-USER-CARBONDB'})
    assert response.status_code == 200, Tests.assertion_info('success', response.text)

    # no filters again for no user
    assert response.text == '{"success":true,"data":{"types":null,"tags":null,"machines":null,"projects":null,"sources":null}}'


def assert_expected_data(exp_data, data):
    for key in exp_data:
        if key == 'ip':
            key = 'ip_address'
        if isinstance(exp_data[key], float):
            assert math.isclose(exp_data[key], data[key], rel_tol=1e-3) , f"{key}: {exp_data[key]} not close to {data[key]} - Raw: {data}"
        else:
            assert exp_data[key] == data[key], f"{key}: {exp_data[key]} != {data[key]} - Raw: {data}"
