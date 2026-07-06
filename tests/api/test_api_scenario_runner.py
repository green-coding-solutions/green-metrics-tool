import os
import requests
import json

import pandas
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib import utils
from lib.job.run import RunJob
from lib import metric_importer
from lib.global_config import GlobalConfig
from lib.phase_stats import build_and_store_phase_stats
from lib.post_metric_providers.calculate_co2_intensity import calculate_co2_intensity
from tests import test_functions as Tests

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

MICROJOULES_TO_KWH = 1/(3_600*1_000_000_000)

RUN_1 = 'a416057b-235f-41d8-9fb8-9bcc70a308e7'
RUN_3 = 'f4ed967e-7c27-4055-815f-ea437fc11d25'
RUN_2 = 'f6167993-260e-41db-ab72-d9c3832f211d'
RUN_4 = '3e6554a4-10bc-46d6-93a1-e61bfd1d9808'

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
    pid = DB().fetch_one("INSERT INTO runs (name,uri,branch,filename,created_at,user_id,machine_id) \
                    VALUES \
                    (%s,%s,'testing','testing',NOW(),1,1) RETURNING id;", params=(run_name, uri))[0]

    response = requests.get(f"{API_URL}/v2/runs?repo=&filename=", timeout=15)
    res_json = response.json()
    assert response.status_code == 200
    assert res_json['data'][0][0] == str(pid)

def test_get_runs_created_after_filter():
    Tests.import_demo_data()

    response_filtered = requests.get(f"{API_URL}/v2/runs?", timeout=15)
    assert response_filtered.status_code == 200
    assert len(response_filtered.json()['data']) == 6

    response_unfiltered = requests.get(f"{API_URL}/v2/runs?start_date=2026-02-17", timeout=15)
    assert response_unfiltered.status_code == 204


    response_filtered = requests.get(f"{API_URL}/v2/runs?start_date=2025-09-01", timeout=15)
    assert response_filtered.status_code == 200
    assert len(response_filtered.json()['data']) == 1


def test_get_jobs_redacts_url_credentials():
    run_name = 'test_' + utils.randomword(12)
    credentialed_url = 'https://admin:s3cr3t@github.com/green-coding-solutions/green-metrics-tool'

    job_id = RunJob.insert(user_id=1, name=run_name, url=credentialed_url, branch='main', filename='usage_scenario.yml', machine_id=1)

    response = requests.get(f"{API_URL}/v2/jobs?job_id={job_id}", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    data = response.json()['data']
    assert data[0][0] == job_id
    assert 'admin' not in data[0][3]
    assert 's3cr3t' not in data[0][3]
    assert '*****GMT-REDACTED*****' in data[0][3]

    # the DB copy must stay usable so the cluster worker can actually clone the repo later
    raw_url = DB().fetch_one('SELECT url FROM jobs WHERE id = %s', params=(job_id,))[0]
    assert raw_url == credentialed_url

def test_compare_valid():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_1}", timeout=15)
    res_json = response.json()
    assert response.status_code == 200

    with open(f"{CURRENT_DIR}/../data/json/compare-{RUN_3},{RUN_1}.json", 'r', encoding='utf-8') as file:
        data = json.load(file)

    assert res_json['data'] == data

def test_compare_fails():
    Tests.import_demo_data()

    DB().query(f"UPDATE runs SET commit_hash = 'test' WHERE id = '{RUN_1}' ")

    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_1},{RUN_2}", timeout=15)
    res_json = response.json()
    assert response.status_code == 422
    assert res_json['err'] == 'Different usage scenarios & commits not supported'

# Will force same style by comparing A vs B. No repeated run style
def test_compare_force_mode_same_style():
    Tests.import_demo_data()

    DB().query(f"UPDATE runs SET commit_hash = 'test' WHERE id = '{RUN_1}' ")

    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_1}&force_mode=usage_scenarios", timeout=15)
    res_json = response.json()
    assert response.status_code == 200

    with open(f"{CURRENT_DIR}/../data/json/compare-{RUN_3},{RUN_1}.json", 'r', encoding='utf-8') as file:
        data = json.load(file)

    # only the hash hash changed, but it will still force the same mode
    data['comparison_details'][0][0]['commit_hash'] = 'test' # we need to overload the test data to make it flexible

    assert data['comparison_case'] == 'Usage Scenario'
    assert res_json['data'] == data

# Will force machine_id comparison, which is repeated_run style
def test_compare_force_mode_different_style():
    Tests.import_demo_data()

    DB().query(f"UPDATE runs SET commit_hash = 'test' WHERE id = '{RUN_1}' ")

    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_1}&force_mode=machine_ids", timeout=15)
    res_json = response.json()
    assert response.status_code == 200

    with open(f"{CURRENT_DIR}/../data/json/compare-{RUN_3},{RUN_1}-machines.json", 'r', encoding='utf-8') as file:
        data = json.load(file)

    # only the hash hash changed, but it will still force the same mode
    data['comparison_details'][0][0]['commit_hash'] = 'test'

    assert data['comparison_case'] == 'Machine'
    assert res_json['data'] == data


def test_compare_ids_mode():
    # Although no proper mode can be found for these two comparisons the mode will be set to IDs
    Tests.import_demo_data()

    DB().query(f"UPDATE runs SET commit_hash = 'test' WHERE id = '{RUN_1}' ")

    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_1}", timeout=15)
    res_json = response.json()
    assert response.status_code == 200

    assert res_json['data']['comparison_case'] == 'IDs'
    assert res_json['data']['comparison_identifiers'] == [RUN_1, RUN_3]

def test_compare_mode_usage_scenario_variables():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_4}", timeout=15)
    res_json = response.json()
    assert response.status_code == 200

    with open(f"{CURRENT_DIR}/../data/json/compare-{RUN_3},{RUN_4}.json", 'r', encoding='utf-8') as file:
        data = json.load(file)

    assert data['comparison_case'] == 'Usage Scenario Variables'
    assert res_json['data'] == data

def test_compare_force_mode_not_writing_to_cache():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_2}", timeout=15)
    res_json = response.json()
    assert response.status_code == 200

    with open(f"{CURRENT_DIR}/../data/json/compare-{RUN_3},{RUN_2}.json", 'r', encoding='utf-8') as file:
        data = json.load(file)

    assert res_json['data'] == data

    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_2}&force_mode=machine_ids", timeout=15)
    res_json = response.json()
    assert response.status_code == 200
    assert res_json['data'] != data

    # test inital call again
    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_2}", timeout=15)
    res_json = response.json()
    assert response.status_code == 200
    assert res_json['data'] == data


def test_compare_force_unknown_mode():
    Tests.import_demo_data()

    DB().query(f"UPDATE runs SET commit_hash = 'test' WHERE id = '{RUN_1}' ")

    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_1}&force_mode=machines", timeout=15)
    res_json = response.json()
    assert response.status_code == 422
    assert res_json['err'] == 'Forcing a comparison mode for unknown mode'

def test_get_insights():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/insights", timeout=15)
    res_json = response.json()
    assert response.status_code == 200
    assert res_json['data'][0] == 6
    assert res_json['data'][1] == '2024-09-11'

def test_get_badge():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/badge/single/{RUN_3}?metric=cpu_energy_rapl_msr_component", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'CPU Package Energy' in response.text, Tests.assertion_info('success', response.text) # nice name - important if JS file was parsed correctly
    assert '12.99 mWh' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/badge/single/{RUN_3}?metric=cpu_energy_rapl_msr_component&unit=joules", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'CPU Package Energy' in response.text, Tests.assertion_info('success', response.text) # nice name - important if JS file was parsed correctly
    assert '46.77 J' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/badge/single/{RUN_3}?metric=phase_time_syscall_system", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Phase Duration' in response.text, Tests.assertion_info('success', response.text) # nice name - important if JS file was parsed correctly
    assert '5.31 s' in response.text, Tests.assertion_info('success', response.text)

    # will not react to Joules
    response = requests.get(f"{API_URL}/v1/badge/single/{RUN_3}?metric=phase_time_syscall_system&unit=joules", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Phase Duration' in response.text, Tests.assertion_info('success', response.text) # nice name - important if JS file was parsed correctly
    assert '5.31 s' in response.text, Tests.assertion_info('success', response.text)


def test_get_badge_with_phase():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/badge/single/{RUN_3}?metric=psu_energy_dc_rapl_msr_machine", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Machine Energy' in response.text, Tests.assertion_info('success', response.text) # nice name - important if JS file was parsed correctly
    assert '21.81 mWh' in response.text, Tests.assertion_info('success', response.text)

    response = requests.get(f"{API_URL}/v1/badge/single/{RUN_3}?metric=psu_energy_dc_rapl_msr_machine&phase=[BOOT]", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert 'Machine Energy {[BOOT]}' in response.text, Tests.assertion_info('success', response.text) # nice name - important if JS file was parsed correctly
    assert '1.85 mWh' in response.text, Tests.assertion_info('success', response.text)


def _import_static_carbon_intensity(run_id, value):
    measurements = []
    for phase in Tests.TEST_MEASUREMENT_PHASES:
        # phase_stats selects with strict time > start AND time < end, so offset slightly
        measurements.append((phase['start'] + 1, value))
        measurements.append((phase['end'] - 1, value))
    df = pandas.DataFrame(measurements, columns=['time', 'value'])
    df['metric'] = 'carbon_intensity_static_machine'
    df['detail_name'] = 'static'
    df['unit'] = 'gCO2e/kWh'
    metric_importer.import_measurements(df, 'carbon_intensity_static_machine', run_id)


def test_phase_stats_single_returns_component_carbon():
    # Regression test: the carbon metric generated for an energy component (e.g. CPU) must
    # actually be retrievable through the /v1/phase_stats/single API, not only the machine carbon.
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    df = Tests.import_cpu_energy(run_id)

    carbon_intensity_value = 436
    _import_static_carbon_intensity(run_id, carbon_intensity_value)

    calculate_co2_intensity(run_id)
    build_and_store_phase_stats(run_id, sci={})

    response = requests.get(f"{API_URL}/v1/phase_stats/single/{run_id}", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)

    runtime_metrics = response.json()['data']['data']['[RUNTIME]']['data']
    assert 'cpu_carbon_rapl_msr_component' in runtime_metrics, 'CPU component carbon metric must be returned through the API'

    cpu_carbon = runtime_metrics['cpu_carbon_rapl_msr_component']
    assert cpu_carbon['unit'] == 'ugCO2e'
    assert cpu_carbon['type'] == 'TOTAL'

    detail = cpu_carbon['data']['Package_0_carbon_intensity_static_machine_static']['data'][str(run_id)]

    cpu_energy = Tests.filter_df_runtime_subphase(df, hidden=False)['value'].sum()
    operational_carbon_expected = int(cpu_energy * MICROJOULES_TO_KWH * carbon_intensity_value * 1_000_000)
    assert detail['mean'] == pytest.approx(operational_carbon_expected, abs=10)
