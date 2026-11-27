import os
import requests
import json

import pandas
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from api.api_helpers import MAX_LOG_CHARS
from lib.db import DB
from lib import utils
from lib.job.run import RunJob
from lib.watchlist import Watchlist
from lib import metric_importer
from lib.global_config import GlobalConfig
from lib.phase_stats import build_and_store_phase_stats
from lib.post_metric_providers.calculate_co2_intensity import calculate_co2_intensity
from tests import test_functions as Tests

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

pytestmark = pytest.mark.xdist_group(name=Tests.GUNICORN_SEQUENTIAL_GROUP)

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
    assert len(response_filtered.json()['data']) == 8

    response_unfiltered = requests.get(f"{API_URL}/v2/runs?start_date=2026-02-17", timeout=15)
    assert response_unfiltered.status_code == 204


    response_filtered = requests.get(f"{API_URL}/v2/runs?start_date=2025-09-01", timeout=15)
    assert response_filtered.status_code == 200
    assert len(response_filtered.json()['data']) == 1


def test_get_runs_pagination():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v2/runs?limit=3&with_count=true", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    first_page = response.json()
    assert len(first_page['data']) == 3
    assert first_page['total'] == 8

    response = requests.get(f"{API_URL}/v2/runs?limit=3&offset=3&with_count=true", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    second_page = response.json()
    assert len(second_page['data']) == 3
    assert second_page['total'] == 8
    assert not {row[0] for row in first_page['data']} & {row[0] for row in second_page['data']}

    response = requests.get(f"{API_URL}/v2/runs?limit=3&offset=6", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert len(response.json()['data']) == 2
    assert 'total' not in response.json()

    # offset beyond the last page still returns the total for paginated tables
    response = requests.get(f"{API_URL}/v2/runs?limit=3&offset=30&with_count=true", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert response.json()['data'] == []
    assert response.json()['total'] == 8

def test_get_runs_limit_bounds():
    response = requests.get(f"{API_URL}/v2/runs?limit=100", timeout=15)
    assert response.status_code in (200, 204), Tests.assertion_info('success', response.text)

    for invalid in ('limit=101', 'limit=0', 'offset=-1', 'order_by=r.id', 'order_dir=sideways'):
        response = requests.get(f"{API_URL}/v2/runs?{invalid}", timeout=15)
        assert response.status_code == 422, Tests.assertion_info(f"422 for {invalid}", response.text)

def test_get_runs_order_and_search():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v2/runs?order_by=name&order_dir=asc&limit=100", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    names = [row[1] for row in response.json()['data']]
    assert names == sorted(names)

    name = names[0]
    response = requests.get(f"{API_URL}/v2/runs?search={name}&with_count=true", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert response.json()['total'] >= 1
    assert all(name.lower() in json.dumps(row).lower() for row in response.json()['data'])

def test_get_repositories_respects_show_archived():
    uri = f"/tmp/archived-repo-{utils.randomword(12)}"
    DB().query("INSERT INTO runs (name,uri,branch,filename,created_at,user_id,machine_id,archived) \
                    VALUES ('archived_run',%s,'testing','testing',NOW(),1,1,TRUE)", params=(uri, ))

    for query_string in ('', '?show_archived=false'):
        response = requests.get(f"{API_URL}/v1/repositories{query_string}", timeout=15)
        assert response.status_code in (200, 204), Tests.assertion_info('success', response.text)
        if response.status_code == 200:
            assert uri not in [row[0] for row in response.json()['data']]

    response = requests.get(f"{API_URL}/v1/repositories?show_archived=true", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert uri in [row[0] for row in response.json()['data']]

def test_get_repositories_respects_show_other_users():
    uri = f"/tmp/other-user-repo-{utils.randomword(12)}"
    DB().query("INSERT INTO runs (name,uri,branch,filename,created_at,user_id,machine_id,public) \
                    VALUES ('other_user_run',%s,'testing','testing',NOW(),0,1,TRUE)", params=(uri, ))

    response = requests.get(f"{API_URL}/v1/repositories?show_other_users=true", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert uri in [row[0] for row in response.json()['data']]

    response = requests.get(f"{API_URL}/v1/repositories?show_other_users=false", timeout=15)
    assert response.status_code in (200, 204), Tests.assertion_info('success', response.text)
    if response.status_code == 200:
        assert uri not in [row[0] for row in response.json()['data']]

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

def test_get_watchlist_never_returns_email():
    run_name = 'test_' + utils.randomword(12)
    email = f"{run_name}@example.com"

    watchlist_id = Watchlist.insert(name=run_name, email=email, image_url='', repo_url='https://github.com/green-coding-solutions/green-metrics-tool', branch='main', filename='usage_scenario.yml', usage_scenario_variables={}, category_ids=None, machine_id=1, user_id=1, schedule_mode='daily', last_marker=None)

    response = requests.get(f"{API_URL}/v1/watchlist", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert watchlist_id in [row[0] for row in response.json()['data']]
    assert email not in response.text

def test_compare_valid():
    Tests.import_demo_data()
    Tests.flush_redis()

    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_1}", timeout=15)
    res_json = response.json()
    assert response.status_code == 200

    with open(f"{CURRENT_DIR}/../data/json/compare-{RUN_3},{RUN_1}.json", 'r', encoding='utf-8') as file:
        data = json.load(file)

    assert res_json['data'] == data

def test_compare_falls_back_to_table_mode():
    Tests.import_demo_data()

    DB().query(f"UPDATE runs SET commit_hash = 'test' WHERE id = '{RUN_1}' ")

    # Auto mode cannot find a single differing attribute here (usage_scenario AND commit_hash
    # differ at once), so it should fall back to the generic per-run 'IDs' table view instead of failing.
    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_1},{RUN_2}", timeout=15)
    assert response.status_code == 409

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
    del data['common_info']['Commit'] # the commits differ now, so they must not be shown as common

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
    del data['common_info']['Commit'] # the commits differ now, so they must not be shown as common

    assert data['comparison_case'] == 'Machine'
    assert res_json['data'] == data


def test_compare_ids_mode():
    # Although no proper mode can be found for these two comparisons the mode will be set to IDs
    Tests.import_demo_data()
    Tests.flush_redis()

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
    Tests.flush_redis()

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

# two IDs used to hit the 'IDs' fallback and crash with a 500 in get_comparison_details(); three+ IDs used to return a misleading 409
@pytest.mark.parametrize('ids', [
    'b3a6c1d0-0000-4000-8000-000000000001,b3a6c1d0-0000-4000-8000-000000000002',
    'b3a6c1d0-0000-4000-8000-000000000001,b3a6c1d0-0000-4000-8000-000000000002,b3a6c1d0-0000-4000-8000-000000000003',
])
@pytest.mark.parametrize('force_mode', [None, 'machine_ids'])
def test_compare_non_existing_runs(ids, force_mode):
    Tests.import_demo_data()

    url = f"{API_URL}/v1/compare?ids={ids}" + (f"&force_mode={force_mode}" if force_mode else '')
    response = requests.get(url, timeout=15)
    assert response.status_code == 404, Tests.assertion_info('not found', response.text)
    assert response.json()['err'] == 'None of the requested runs exist or you do not have access to them'

@pytest.mark.parametrize('ids', [f"{RUN_3},{RUN_1}", f"{RUN_3},{RUN_1},{RUN_2}"])
def test_compare_runs_not_visible_for_user(ids):
    Tests.import_demo_data()
    Tests.insert_user(2, 'OTHER_USER')

    response = requests.get(f"{API_URL}/v1/compare?ids={ids}", headers={'X-Authentication': 'OTHER_USER'}, timeout=15)
    assert response.status_code == 404, Tests.assertion_info('not found', response.text)
    assert response.json()['err'] == 'None of the requested runs exist or you do not have access to them'

RUN_NO_PHASE_STATS = 'af76f822-c042-4bf1-a5aa-5566761ef351' # stress/usage_scenario.yml, same config as RUN_3 and RUN_2
RUN_DIFFERENT_SCENARIO = '6f07bd8a-ac53-47aa-a9df-17417a72238b' # different/usage_scenario.yml, same config as RUN_1
OTHER_REPO = "uri = 'https://example.com/other-repo', commit_hash = 'other'"

# Repository and Branch mode allow e.g. two usage scenarios in total, but each group must only have one.
# Otherwise the runs of one group would be averaged over different configurations, so these must fall back to the table view
@pytest.mark.parametrize('updates, ids', [
    ([f"UPDATE runs SET {OTHER_REPO} WHERE id = '{RUN_2}'"], [RUN_3, RUN_4, RUN_2]), # repo A has two variable sets
    ([f"UPDATE runs SET {OTHER_REPO} WHERE id = '{RUN_2}'"], [RUN_3, RUN_DIFFERENT_SCENARIO, RUN_2]), # repo A has two usage scenarios
    ([f"UPDATE runs SET branch = 'dev' WHERE id = '{RUN_2}'", f"UPDATE runs SET {OTHER_REPO} WHERE id = '{RUN_1}'"], [RUN_3, RUN_2, RUN_1]), # repo A has two branches
    ([f"UPDATE runs SET uri = 'https://example.com/fork' WHERE id = '{RUN_2}'", f"UPDATE runs SET commit_hash = 'c2' WHERE id = '{RUN_3}'"], [RUN_NO_PHASE_STATS, RUN_3, RUN_2]), # repo A has two commits, its fork shares one
    ([f"UPDATE runs SET branch = 'feature' WHERE id = '{RUN_NO_PHASE_STATS}'", f"UPDATE runs SET commit_hash = 'c2' WHERE id = '{RUN_2}'"], [RUN_3, RUN_2, RUN_NO_PHASE_STATS]), # main has two commits, feature shares one
])
def test_compare_mixed_configurations_within_group_fall_back_to_table_mode(updates, ids):
    Tests.import_demo_data()
    Tests.flush_redis()
    for update in updates:
        DB().query(update)

    response = requests.get(f"{API_URL}/v1/compare?ids={','.join(ids)}", timeout=15)
    assert response.status_code == 409, Tests.assertion_info('fallback to table mode', response.text)

@pytest.mark.parametrize('update, ids, comparison_case, comparison_identifiers', [
    (f"UPDATE runs SET {OTHER_REPO} WHERE id = '{RUN_1}'", [RUN_3, RUN_2, RUN_1], 'Repository', ['https://example.com/other-repo', '/home/arne/Sites/green-coding/example-applications/']),
    (f"UPDATE runs SET branch = 'feature', commit_hash = 'c2' WHERE id = '{RUN_NO_PHASE_STATS}'", [RUN_3, RUN_2, RUN_NO_PHASE_STATS], 'Branch', ['feature', 'main']),
])
def test_compare_one_configuration_per_group(update, ids, comparison_case, comparison_identifiers):
    Tests.import_demo_data()
    Tests.flush_redis()
    DB().query(update)

    response = requests.get(f"{API_URL}/v1/compare?ids={','.join(ids)}", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert response.json()['data']['comparison_case'] == comparison_case
    assert response.json()['data']['comparison_identifiers'] == comparison_identifiers

def test_get_insights():
    Tests.import_demo_data()

    response = requests.get(f"{API_URL}/v1/insights", timeout=15)
    res_json = response.json()
    assert response.status_code == 200
    assert res_json['data'][0] == 8
    assert res_json['data'][1] == '2023-09-11'

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

def _insert_run_with_logs(logs):
    return DB().fetch_one(
        """
        INSERT INTO runs (name, uri, branch, filename, machine_id, user_id, logs, created_at)
        VALUES ('Log run', 'https://www.example.com', 'main', 'usage_scenario.yml', 1, 1, %s, NOW())
        RETURNING id
        """,
        params=(None if logs is None else json.dumps(logs), )
    )[0]

def _log_entry(**streams):
    return {'type': 'flow_command', 'id': '1', 'cmd': 'ls', 'phase': None, **streams}

def test_get_run_does_not_return_logs():
    run_id = _insert_run_with_logs({'ctr': [_log_entry(stdout='a')]})

    response = requests.get(f"{API_URL}/v2/run/{run_id}", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)

    assert 'logs' not in response.json()['data']

def test_get_logs_returns_unclipped_logs():
    logs = {
        'ctr': [_log_entry(stdout='a' * (MAX_LOG_CHARS + 1), stderr='b'), _log_entry()],
        '[SYSTEM]': [_log_entry(stderr='exception')],
    }

    response = requests.get(f"{API_URL}/v1/logs/{_insert_run_with_logs(logs)}", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)

    assert response.json()['data'] == logs

@pytest.mark.parametrize('logs', [None, {}])
def test_get_logs_of_run_without_logs(logs):
    response = requests.get(f"{API_URL}/v1/logs/{_insert_run_with_logs(logs)}", timeout=15)

    assert response.status_code == 204, Tests.assertion_info('no content', response.text)

def test_get_logs_invalid_run_id():
    response = requests.get(f"{API_URL}/v1/logs/not-a-uuid", timeout=15)

    assert response.status_code == 422, Tests.assertion_info('invalid run id', response.text)

def test_get_logs_only_visible_for_allowed_users():
    Tests.insert_user(2, 'OTHER_USER')
    run_id = _insert_run_with_logs({'ctr': [_log_entry(stdout='secret')]})
    headers = {'X-Authentication': 'OTHER_USER'}

    response = requests.get(f"{API_URL}/v1/logs/{run_id}", headers=headers, timeout=15)
    assert response.status_code == 204, Tests.assertion_info('no content', response.text)

    DB().query('UPDATE runs SET public = TRUE WHERE id = %s', params=(run_id, ))

    response = requests.get(f"{API_URL}/v1/logs/{run_id}", headers=headers, timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert response.json()['data'] == {'ctr': [_log_entry(stdout='secret')]}

def _insert_run_with_metric_providers(configured_metric_providers):
    return DB().fetch_one(
        """
        INSERT INTO runs (name, uri, branch, filename, machine_id, user_id, measurement_config, created_at)
        VALUES ('Network run', 'https://www.example.com', 'main', 'usage_scenario.yml', 1, 1, %s, NOW())
        RETURNING id
        """,
        params=(json.dumps({'configured_metric_providers': configured_metric_providers}), )
    )[0]

def test_get_network_provider_not_active():
    run_id = _insert_run_with_metric_providers({'cpu_utilization_procfs_system': {'sampling_rate': 99}})

    response = requests.get(f"{API_URL}/v1/network/{run_id}", timeout=15)
    assert response.status_code == 422, Tests.assertion_info('provider not active', response.text)
    assert response.json()['err'] == 'Network connections metric provider was not active for this run'

@pytest.mark.parametrize('provider', ['network_connections_proxy_container', 'network.connections.proxy.container.provider.NetworkConnectionsProxyContainerProvider'])
def test_get_network_provider_active_without_connections(provider):
    run_id = _insert_run_with_metric_providers({provider: None})

    response = requests.get(f"{API_URL}/v1/network/{run_id}", timeout=15)
    assert response.status_code == 204, Tests.assertion_info('no content', response.text)

def test_get_network_provider_active_with_connections():
    run_id = _insert_run_with_metric_providers({'network_connections_proxy_container': None})
    DB().query(
        "INSERT INTO network_intercepts (run_id, time, connection_type, protocol) VALUES (%s, 1700000000000, 'example.com:443', 'HTTPS')",
        params=(run_id, )
    )

    response = requests.get(f"{API_URL}/v1/network/{run_id}", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert [row[3:5] for row in response.json()['data']] == [['example.com:443', 'HTTPS']]

def test_get_network_run_not_visible():
    Tests.insert_user(2, 'OTHER_USER')
    run_id = _insert_run_with_metric_providers({'network_connections_proxy_container': None})

    response = requests.get(f"{API_URL}/v1/network/{run_id}", headers={'X-Authentication': 'OTHER_USER'}, timeout=15)
    assert response.status_code == 404, Tests.assertion_info('not found', response.text)

def test_get_system_logs_clips_message():
    DB().query(
        "INSERT INTO system_logs (id, title, message) VALUES (1, 'long', %s), (2, 'at limit', %s)",
        params=('a' * (MAX_LOG_CHARS + 1), 'b' * MAX_LOG_CHARS)
    )

    response = requests.get(f"{API_URL}/v1/system-logs", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)

    rows = {row[0]: row for row in response.json()['data']}
    assert rows[1][2] == 'a' * MAX_LOG_CHARS
    assert rows[1][5] is True
    assert rows[2][2] == 'b' * MAX_LOG_CHARS
    assert rows[2][5] is False

def test_compare_common_info_only_contains_identical_values():
    Tests.import_demo_data()
    Tests.flush_redis()

    # Repository mode allows a different branch per repo. Branch must then not be shown as common
    DB().query(f"UPDATE runs SET uri = 'https://example.com/other-repo', commit_hash = 'other', branch = 'master' WHERE id = '{RUN_1}'")

    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_2},{RUN_1}", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    res_json = response.json()

    assert res_json['data']['comparison_case'] == 'Repository'
    assert res_json['data']['common_info'] == {'Machine': 'Development machine for testing'}

def test_compare_common_info_force_mode():
    Tests.import_demo_data()

    # force_mode skips all checks. RUN_3 and RUN_1 differ in filename, which must not be shown as common
    response = requests.get(f"{API_URL}/v1/compare?ids={RUN_3},{RUN_1}&force_mode=machine_ids", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    res_json = response.json()

    assert res_json['data']['comparison_case'] == 'Machine'
    assert res_json['data']['common_info'] == {
        'Repository': '/home/arne/Sites/green-coding/example-applications/',
        'Usage Scenario': 'Stress Container One Core 5 Seconds',
        'Branch': 'main',
        'Commit': '58c7a5002c684f41f8d7a355f3ede641d8e45ddc',
    }
