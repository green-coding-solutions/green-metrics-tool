import os
import requests
import subprocess
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

pytestmark = pytest.mark.xdist_group(name=Tests.GUNICORN_SEQUENTIAL_GROUP)

def test_ci_deprecated_endpoint():
    response = requests.post(f"{API_URL}/v1/ci/measurement/add", json={}, timeout=15)
    assert response.status_code == 410, Tests.assertion_info('success', response.text)

MEASUREMENT_MODEL_V3 = {'energy_uj': 123000,
                        'repo': 'testRepo',
                        'branch': 'testBranch',
                        'cpu': 'testCPU',
                        'cpu_util_avg': 50,
                        'commit_hash': '1234asdf',
                        'workflow': 'testWorkflow',
                        'run_id': 'testRunID',
                        'source': 'testSource',
                        'label': 'testLabel',
                        'duration_us': 20000,
                        'workflow_name': 'testWorkflowName',
                        'os_name': 'testOsName',
                        'cpu_arch': 'testCpuArch',
                        'job_id': 'testJobID',
                        'version': 'v2.2'}

# v4 renamed workflow -> workflow_id. Carbon fields differ and are set per test
MEASUREMENT_MODEL_V4 = {('workflow_id' if key == 'workflow' else key): value for key, value in MEASUREMENT_MODEL_V3.items()}

# Tests that behave identically for v3 and v4 run for both
BOTH_VERSIONS = pytest.mark.parametrize('version, measurement_model_base', [('v3', MEASUREMENT_MODEL_V3), ('v4', MEASUREMENT_MODEL_V4)])

def test_ci_removed_v2_endpoint():
    response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=MEASUREMENT_MODEL_V3, timeout=15)
    assert response.status_code == 404, Tests.assertion_info('404', response.text)

@BOTH_VERSIONS
def test_ci_measurement_add_default_user(version, measurement_model_base):

    measurement_model = measurement_model_base.copy()

    response = requests.post(f"{API_URL}/{version}/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_data(measurement_model, data)

    assert data['user_id'] == 1
    # assert the defaults set by the model
    assert data['filter_type'] == 'machine.ci'
    assert data['filter_machine'] == 'unknown'
    assert data['filter_project'] == 'CI/CD'
    assert data['filter_tags'] == []

@BOTH_VERSIONS
def test_ci_measurement_add_different_user(version, measurement_model_base):

    Tests.insert_user(2, 'PYTEST')

    measurement_model = measurement_model_base.copy()

    response = requests.post(f"{API_URL}/{version}/ci/measurement/add", json=measurement_model, timeout=15, headers={'X-Authentication': 'PYTEST'})
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_data(measurement_model, data)

    assert data['user_id'] == 2

@BOTH_VERSIONS
def test_ci_measurement_add_small_with_warning(version, measurement_model_base):

    measurement_model = measurement_model_base.copy()
    measurement_model['energy_uj'] = 1

    response = requests.post(f"{API_URL}/{version}/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)
    logs = subprocess.check_output(['docker', 'logs', 'test-green-coding-gunicorn-container', '-n', '10'], stderr=subprocess.STDOUT, encoding='UTF-8').strip()

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_data(measurement_model, data)

    assert 'Extremely small energy / carbon value was submitted to Eco CI API' in logs
    assert f"Measurement (CI_Measurement{version.upper()}): energy_uj=1" in logs

@BOTH_VERSIONS
def test_ci_measurement_add_force_ip(version, measurement_model_base):

    measurement_model = measurement_model_base.copy()
    measurement_model['ip'] = '1.1.1.1'

    response = requests.post(f"{API_URL}/{version}/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])

    data['ip'] = str(data['ip_address']) # model as a different key in DB
    del data['ip_address']

    compare_data(measurement_model, data)

@BOTH_VERSIONS
def test_ci_measurement_add_filters(version, measurement_model_base):

    measurement_model = measurement_model_base.copy()

    measurement_model['filter_tags'] = ["asd", "Mit space"]
    measurement_model['filter_project'] = 'Das ist cool'
    measurement_model['filter_type'] = 'CI / CD'

    response = requests.post(f"{API_URL}/{version}/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_data(measurement_model, data)

@BOTH_VERSIONS
@pytest.mark.parametrize('filter_key', ['filter_type', 'filter_project', 'filter_machine'])
def test_ci_measurement_add_whitespace_filter_rejected(version, measurement_model_base, filter_key):
    # filter_* are NOT NULL in the DB. A whitespace value used to be turned into None, which crashed the insert with a 500
    measurement_model = measurement_model_base.copy()
    measurement_model[filter_key] = '  '

    response = requests.post(f"{API_URL}/{version}/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 422, Tests.assertion_info('422', response.text)
    assert f"{filter_key} must be set and non-empty" in response.text

@BOTH_VERSIONS
def test_ci_measurement_add_empty_optionals_stored_as_null(version, measurement_model_base):

    measurement_model = measurement_model_base.copy()
    measurement_model['lat'] = ''
    measurement_model['lon'] = ' '
    measurement_model['city'] = ''
    measurement_model['ip'] = ''
    measurement_model['note'] = '  '

    response = requests.post(f"{API_URL}/{version}/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    assert data['latitude'] is None
    assert data['longitude'] is None
    assert data['city'] is None
    assert data['note'] is None
    assert data['ip_address'] is not None # connecting IP is used instead

def test_ci_measurement_add_numbers_as_strings_rejected_v4():
    # v3 coerces strings like "123000". v4 requires JSON numbers
    for key in ['energy_uj', 'cpu_util_avg', 'duration_us']:
        measurement_model = MEASUREMENT_MODEL_V4.copy()
        measurement_model[key] = str(measurement_model[key])

        response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
        assert response.status_code == 422, Tests.assertion_info(f"422 for {key}", response.text)

def test_ci_measurement_add_workflow_renamed_v4():
    measurement_model = MEASUREMENT_MODEL_V4.copy()
    measurement_model['workflow'] = measurement_model.pop('workflow_id')

    response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 422, Tests.assertion_info('422', response.text)
    assert 'workflow_id' in response.text

def test_ci_measurement_add_workflow_name_required_v4():
    measurement_model = MEASUREMENT_MODEL_V4.copy()
    del measurement_model['workflow_name']

    response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 422, Tests.assertion_info('422', response.text)

    measurement_model['workflow_name'] = ' '
    response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 422, Tests.assertion_info('422', response.text)

    # v3 keeps workflow_name optional
    measurement_model = MEASUREMENT_MODEL_V3.copy()
    del measurement_model['workflow_name']
    response = requests.post(f"{API_URL}/v3/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

def test_ci_measurement_add_co2_v4():

    measurement_model = MEASUREMENT_MODEL_V4.copy()

    measurement_model['lat'] = '18.2972'
    measurement_model['lon'] = '77.2793'
    measurement_model['city'] = 'Nine Mile'
    measurement_model['carbon_intensity_g'] = 100
    measurement_model['operational_carbon_ug'] = 4567893453245
    measurement_model['embodied_carbon_ug'] = 1234

    response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_data(measurement_model, data)

    assert 'carbon_ug' not in data # combined value is not stored anymore

def test_ci_measurement_add_embodied_carbon_only_v4():

    measurement_model = MEASUREMENT_MODEL_V4.copy()
    measurement_model['embodied_carbon_ug'] = 1234

    response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_data(measurement_model, data)

    assert data['operational_carbon_ug'] is None

def test_ci_measurement_add_total_carbon_rejected_v4():

    measurement_model = MEASUREMENT_MODEL_V4.copy()
    measurement_model['carbon_ug'] = 1234

    response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 422, Tests.assertion_info('422', response.text)


def test_ci_badge_duration_error():
    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=avg&duration_days=900", timeout=15)
    assert response.status_code == 422
    assert response.text == '{"success":false,"err":"Duration days must be between 1 and 365 days"}'


def test_ci_badge_get_last():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=last", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Last run energy used' in response.text, Tests.assertion_info('success', response.text)
    assert '8.04 mWh' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=last&unit=joules", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Last run energy used' in response.text, Tests.assertion_info('success', response.text)
    assert '28.95 J' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=last&metric=carbon", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Last run carbon emitted' in response.text, Tests.assertion_info('success', response.text)
    assert '0.02 g' in response.text, Tests.assertion_info('success', response.text)


def test_ci_badge_get_totals():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=totals", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'All runs total energy used' in response.text, Tests.assertion_info('success', response.text)
    assert '13617.37 mWh' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=totals&unit=joules", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'All runs total energy used' in response.text, Tests.assertion_info('success', response.text)
    assert '49022.55 J' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo=green-coding-solutions/ci-carbon-testing&branch=main&workflow=48163287&mode=totals&metric=carbon", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'All runs total carbon emitted' in response.text, Tests.assertion_info('success', response.text)
    assert '15.56 g' in response.text, Tests.assertion_info('success', response.text)


def test_ci_badge_get_average_v4():

    for i in range(1,3):
        measurement_model = MEASUREMENT_MODEL_V4.copy()
        measurement_model['operational_carbon_ug'] = 600
        measurement_model['embodied_carbon_ug'] = 400
        response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
        assert response.status_code == 202, Tests.assertion_info('success', response.text)

    for i in range(1,6):
        measurement_model = MEASUREMENT_MODEL_V4.copy()
        measurement_model['energy_uj'] *= 1000
        measurement_model['operational_carbon_ug'] = i*60000
        measurement_model['embodied_carbon_ug'] = i*40000
        measurement_model['run_id'] = 'Other run'
        response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
        assert response.status_code == 202, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo={MEASUREMENT_MODEL_V4['repo']}&branch={MEASUREMENT_MODEL_V4['branch']}&workflow={MEASUREMENT_MODEL_V4['workflow_id']}&mode=avg&duration_days=5&unit=joules", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Per run moving average (5 days) energy used' in response.text, Tests.assertion_info('success', response.text)
    assert '307.62 J' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo={MEASUREMENT_MODEL_V4['repo']}&branch={MEASUREMENT_MODEL_V4['branch']}&workflow={MEASUREMENT_MODEL_V4['workflow_id']}&mode=avg&duration_days=5", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Per run moving average (5 days) energy used' in response.text, Tests.assertion_info('success', response.text)
    assert '85.45 mWh' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo={MEASUREMENT_MODEL_V4['repo']}&branch={MEASUREMENT_MODEL_V4['branch']}&workflow={MEASUREMENT_MODEL_V4['workflow_id']}&mode=avg&duration_days=5&metric=carbon", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)

    assert 'Per run moving average (5 days) carbon emitted' in response.text, Tests.assertion_info('success', response.text)
    assert '0.75 g' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo={MEASUREMENT_MODEL_V4['repo']}&branch={MEASUREMENT_MODEL_V4['branch']}&workflow={MEASUREMENT_MODEL_V4['workflow_id']}&mode=avg&duration_days=5&metric=operational_carbon", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Per run moving average (5 days) operational carbon emitted' in response.text, Tests.assertion_info('success', response.text)
    assert '0.45 g' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo={MEASUREMENT_MODEL_V4['repo']}&branch={MEASUREMENT_MODEL_V4['branch']}&workflow={MEASUREMENT_MODEL_V4['workflow_id']}&mode=avg&duration_days=5&metric=embodied_carbon", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Per run moving average (5 days) embodied carbon emitted' in response.text, Tests.assertion_info('success', response.text)
    assert '0.30 g' in response.text, Tests.assertion_info('success', response.text)

def test_ci_badge_carbon_needs_both_parts():
    measurement_model = MEASUREMENT_MODEL_V4.copy()
    measurement_model['embodied_carbon_ug'] = 400 # operational part still missing, e.g. waiting for carbon intensity backfill

    response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo={MEASUREMENT_MODEL_V4['repo']}&branch={MEASUREMENT_MODEL_V4['branch']}&workflow={MEASUREMENT_MODEL_V4['workflow_id']}&mode=totals&metric=carbon", timeout=15)
    assert response.status_code == 204, Tests.assertion_info('no total, as a part is missing', response.text)

    response = requests.get(f"{API_URL}/v1/ci/badge/get?repo={MEASUREMENT_MODEL_V4['repo']}&branch={MEASUREMENT_MODEL_V4['branch']}&workflow={MEASUREMENT_MODEL_V4['workflow_id']}&mode=totals&metric=embodied_carbon", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)


def test_get_insights():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/ci/insights", timeout=15)
    res_json = response.json()
    assert response.status_code == 200
    assert res_json['data'][0] == 453
    assert res_json['data'][1] == '2023-08-01'

# tests for the carbon split of /v3/ci/measurement/add
def test_ci_measurement_add_co2_v3():

    measurement_model = MEASUREMENT_MODEL_V3.copy()

    measurement_model['lat'] = '18.2972'
    measurement_model['lon'] = '77.2793'
    measurement_model['city'] = 'Nine Mile'
    measurement_model['carbon_intensity_g'] = 100
    measurement_model['carbon_ug'] = 4567893453245

    response = requests.post(f"{API_URL}/v3/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_data(measurement_model, data)

    # operational = 123000 uJ * 100 g/kWh / 3_600_000 = 3.4 -> 3 ug. Remainder is embodied
    assert data['operational_carbon_ug'] == 3
    assert data['embodied_carbon_ug'] == 4567893453245 - 3

def test_ci_measurement_add_carbon_without_intensity_v3():

    measurement_model = MEASUREMENT_MODEL_V3.copy()
    measurement_model['carbon_ug'] = 5000

    response = requests.post(f"{API_URL}/v3/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    compare_data(measurement_model, data)

    # without carbon intensity no operational carbon can have been calculated, so it can only be embodied
    assert data['operational_carbon_ug'] is None
    assert data['embodied_carbon_ug'] == 5000

def test_ci_measurement_add_carbon_smaller_than_operational_v3():

    measurement_model = MEASUREMENT_MODEL_V3.copy()
    measurement_model['energy_uj'] = 36_000_000_000
    measurement_model['carbon_intensity_g'] = 100
    measurement_model['carbon_ug'] = 999_000 # operational alone is 1_000_000. Can happen through rounding in the client

    response = requests.post(f"{API_URL}/v3/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    assert data['operational_carbon_ug'] == 1_000_000
    assert data['embodied_carbon_ug'] == 0

def test_ci_measurement_add_no_carbon_v3():

    measurement_model = MEASUREMENT_MODEL_V3.copy()
    measurement_model['carbon_intensity_g'] = 100

    response = requests.post(f"{API_URL}/v3/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    data = fetch_data_from_db(measurement_model['run_id'])
    assert data['operational_carbon_ug'] is None # filled later by cron/backfill_carbon_intensity.py
    assert data['embodied_carbon_ug'] is None

def test_ci_measurements_v1_deprecated():
    response = requests.get(f"{API_URL}/v1/ci/measurements?repo=testRepo&branch=testBranch&workflow=testWorkflow&start_date=1970-01-01&end_date=3000-01-01", timeout=15)
    assert response.status_code == 410, Tests.assertion_info('410', response.text)
    assert 'operational and embodied carbon' in response.json()['err']
    assert '/v2/ci/measurements' in response.json()['err']

def test_ci_measurements_v2():
    measurement_model = MEASUREMENT_MODEL_V4.copy()
    measurement_model['carbon_intensity_g'] = 100
    measurement_model['operational_carbon_ug'] = 300
    measurement_model['embodied_carbon_ug'] = 200
    measurement_model['note'] = 'testNote'

    response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v2/ci/measurements?repo={measurement_model['repo']}&branch={measurement_model['branch']}&workflow={measurement_model['workflow_id']}&start_date=1970-01-01&end_date=3000-01-01", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    row = response.json()['data'][0]
    assert row[0] == measurement_model['energy_uj']
    assert row[13] == 100 # carbon_intensity_g
    assert row[14] == 300 # operational_carbon_ug
    assert row[15] == 200 # embodied_carbon_ug
    assert row[16] == 'testNote'
    assert row[17] == 500 # total carbon

def test_ci_stats_v1_deprecated():
    response = requests.get(f"{API_URL}/v1/ci/stats?repo=testRepo&branch=testBranch&workflow=testWorkflow&start_date=1970-01-01&end_date=3000-01-01", timeout=15)
    assert response.status_code == 410, Tests.assertion_info('410', response.text)
    assert 'operational and embodied carbon' in response.json()['err']
    assert '/v2/ci/stats' in response.json()['err']

def test_ci_stats_v2_total_carbon_only_over_complete_runs():
    # Run A is complete. Run B has no operational carbon yet (e.g. waiting for the carbon intensity backfill)
    # Adding up the component averages would give 1000 + 2000 = 3000 ug, which matches no run
    for run_id, operational_carbon_ug, embodied_carbon_ug in [('A', 1000, 1000), ('B', None, 3000)]:
        measurement_model = MEASUREMENT_MODEL_V4.copy()
        measurement_model['run_id'] = run_id
        measurement_model['operational_carbon_ug'] = operational_carbon_ug
        measurement_model['embodied_carbon_ug'] = embodied_carbon_ug
        response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
        assert response.status_code == 202, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v2/ci/stats?repo={MEASUREMENT_MODEL_V4['repo']}&branch={MEASUREMENT_MODEL_V4['branch']}&workflow={MEASUREMENT_MODEL_V4['workflow_id']}&start_date=1970-01-01&end_date=3000-01-01", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    totals = response.json()['data']['totals']
    per_label = response.json()['data']['per_label']

    assert totals[16] == 1000 # AVG operational, only run A
    assert totals[20] == 2000 # AVG embodied, runs A and B
    assert totals[24] == 2000 # AVG total, only complete run A
    assert totals[25] == 2000 # SUM total, only complete run A
    assert totals[28] == 2 # run count

    assert len(per_label) == 1
    assert per_label[0][24] == 2000 # AVG total, only the complete measurement
    assert per_label[0][28] == 2 # measurement count
    assert per_label[0][29] == MEASUREMENT_MODEL_V4['label']

def test_ci_stats_v2_total_carbon_of_partially_complete_run():
    # One measurement of the run lacks operational carbon. So the total of the whole run is unknown
    for operational_carbon_ug, embodied_carbon_ug in [(600, 400), (None, 2000)]:
        measurement_model = MEASUREMENT_MODEL_V4.copy()
        measurement_model['operational_carbon_ug'] = operational_carbon_ug
        measurement_model['embodied_carbon_ug'] = embodied_carbon_ug
        response = requests.post(f"{API_URL}/v4/ci/measurement/add", json=measurement_model, timeout=15)
        assert response.status_code == 202, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v2/ci/stats?repo={MEASUREMENT_MODEL_V4['repo']}&branch={MEASUREMENT_MODEL_V4['branch']}&workflow={MEASUREMENT_MODEL_V4['workflow_id']}&start_date=1970-01-01&end_date=3000-01-01", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    totals = response.json()['data']['totals']
    assert totals[17] == 600 # SUM operational
    assert totals[21] == 2400 # SUM embodied
    assert totals[24] is None # AVG total unknown, as the only run is incomplete
    assert totals[25] is None

def test_ci_measurement_v3_deprecated():
    response = requests.get(f"{API_URL}/openapi.json", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    paths = response.json()['paths']
    assert paths['/v3/ci/measurement/add']['post'].get('deprecated') is True
    assert paths['/v4/ci/measurement/add']['post'].get('deprecated') is None
    assert paths['/v1/ci/measurements']['get'].get('deprecated') is True
    assert paths['/v2/ci/measurements']['get'].get('deprecated') is None
    assert paths['/v1/ci/stats']['get'].get('deprecated') is True
    assert paths['/v2/ci/stats']['get'].get('deprecated') is None


## helpers

def fetch_data_from_db(run_id):
    query = 'SELECT * FROM ci_measurements WHERE run_id = %s' # we make * match to always test all columns. Even if we add some in the future. However they must be part of the CI_MeasurementV3 / CI_MeasurementV4 models
    return DB().fetch_one(query, (run_id, ), fetch_mode='dict')

def compare_data(measurement_model, data):
    for key in measurement_model.keys():
        if key in ['workflow', 'carbon_ug']: continue # v3 only: workflow is stored as workflow_id, carbon_ug is stored split up. Tests check the split explicitly
        if key == 'lat':
            assert data['latitude'] == float(measurement_model[key])
        elif key == 'lon':
            assert data['longitude'] == float(measurement_model[key])
        else:
            assert data[key] == measurement_model[key]
