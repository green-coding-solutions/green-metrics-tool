import os
import requests
import math

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.global_config import GlobalConfig
from lib.db import DB
from tests import test_functions as Tests

from cron.carbondb_compress import compress_carbondb_raw
from cron.carbondb_copy_over_and_remove_duplicates import copy_over_scenario_runner, copy_over_eco_ci, remove_duplicates


API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

from tests.api.test_api_eco_ci import MEASUREMENT_MODEL_NEW as ECO_CI_DATA
from tests.api.test_api_carbondb import ENERGY_DATA

FROM_J_TO_KWH = 3_600 * 1_000
FROM_UJ_TO_J = FROM_UG_TO_G = 1_000_000
FROM_G_TO_KG = 1_000
FROM_UG_TO_KG = 1_000_000_000

def test_insert_and_compress_eco_ci_with_two_users():

    print(GlobalConfig().config)
    RANGE_AMOUNT = 10

    Tests.insert_user(345, 'ALTERNATIVE-USER')

    eco_ci_data = ECO_CI_DATA.copy()
    eco_ci_data['carbon_ug'] = 7

    eco_ci_data_2 = ECO_CI_DATA.copy()
    eco_ci_data_2['carbon_ug'] = 400


    for _ in range(RANGE_AMOUNT):
        response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=eco_ci_data, timeout=15)
        assert response.status_code == 202, Tests.assertion_info('success', response.text)

        response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=eco_ci_data_2, timeout=15, headers={'X-Authentication': 'ALTERNATIVE-USER'})
        assert response.status_code == 202, Tests.assertion_info('success', response.text)

    copy_over_eco_ci()
    compress_carbondb_raw()

    data = DB().fetch_one('SELECT * FROM carbondb_data WHERE date = CURRENT_DATE AND user_id = 1', fetch_mode='dict')

    energy_kWh =  eco_ci_data['energy_uj'] * RANGE_AMOUNT / FROM_UJ_TO_J / FROM_J_TO_KWH
    assert math.isclose(data['energy_kwh_sum'], energy_kWh, rel_tol=1e-5)

    carbon_kg = eco_ci_data['carbon_ug'] * RANGE_AMOUNT / FROM_UG_TO_KG
    assert math.isclose(data['carbon_kg_sum'], carbon_kg, rel_tol=1e-5)

    carbon_intensity_g_avg = int((carbon_kg/energy_kWh)*1000)
    assert carbon_intensity_g_avg-1 <= data['carbon_intensity_g_avg'] <= carbon_intensity_g_avg+1 # different rounding can cost 1 g different intensity. No need to be more precise here given that the margin of error in the source data is not know

    data = DB().fetch_one('SELECT * FROM carbondb_data WHERE date = CURRENT_DATE and user_id = 345', fetch_mode='dict')

    energy_kWh = eco_ci_data_2['energy_uj'] * RANGE_AMOUNT / FROM_UJ_TO_J / FROM_J_TO_KWH
    assert math.isclose(data['energy_kwh_sum'], energy_kWh, rel_tol=1e-5)

    carbon_kg = eco_ci_data_2['carbon_ug'] * RANGE_AMOUNT / FROM_UG_TO_KG
    assert math.isclose(data['carbon_kg_sum'], carbon_kg, rel_tol=1e-5)

    carbon_intensity_g_avg = int((carbon_kg/energy_kWh)*1000)
    assert carbon_intensity_g_avg-1 <= data['carbon_intensity_g_avg'] <= carbon_intensity_g_avg+1 # different rounding can cost 1 g different intensity. No need to be more precise here given that the margin of error in the source data is not know

def test_insert_and_compress_carbondb_with_two_users():

    RANGE_AMOUNT = 10

    Tests.insert_user(345, 'ALTERNATIVE-USER')

    energy_data = ENERGY_DATA.copy()
    energy_data['carbon_intensity_g'] = 200

    energy_data_2 = ENERGY_DATA.copy()
    energy_data_2['energy_uj'] = 300
    energy_data_2['carbon_intensity_g'] = 200


    for _ in range(RANGE_AMOUNT):

        response = requests.post(f"{API_URL}/v2/carbondb/add", json=energy_data, timeout=15)
        assert response.status_code == 202, Tests.assertion_info('success', response.text)

        response = requests.post(f"{API_URL}/v2/carbondb/add", json=energy_data_2, timeout=15, headers={'X-Authentication': 'ALTERNATIVE-USER'})
        assert response.status_code == 202, Tests.assertion_info('success', response.text)

    compress_carbondb_raw()

    data = DB().fetch_one('SELECT * FROM carbondb_data WHERE date = CURRENT_DATE and user_id = 1', fetch_mode='dict')
    energy_kWh = energy_data['energy_uj'] * RANGE_AMOUNT / FROM_UJ_TO_J / FROM_J_TO_KWH
    assert math.isclose(data['energy_kwh_sum'], energy_kWh, rel_tol=1e-5)

    carbon_kg = energy_kWh * energy_data['carbon_intensity_g'] / FROM_G_TO_KG
    assert math.isclose(data['carbon_kg_sum'], carbon_kg, rel_tol=1e-5)

    assert data['carbon_intensity_g_avg'] == energy_data['carbon_intensity_g']


    data = DB().fetch_one('SELECT * FROM carbondb_data WHERE date = CURRENT_DATE and user_id = 345', fetch_mode='dict')
    energy_kWh = energy_data_2['energy_uj'] * RANGE_AMOUNT / FROM_UJ_TO_J / FROM_J_TO_KWH
    assert math.isclose(data['energy_kwh_sum'], energy_kWh, rel_tol=1e-5)

    carbon_kg = energy_kWh * energy_data_2['carbon_intensity_g'] / FROM_G_TO_KG
    assert math.isclose(data['carbon_kg_sum'], carbon_kg, rel_tol=1e-5)

    assert data['carbon_intensity_g_avg'] == energy_data_2['carbon_intensity_g']


def test_insert_and_compress_gmt_with_two_users():

    AMOUNT_OF_GMT_RUNS = 9

    Tests.insert_user(345, 'ALTERNATIVE-USER')
    Tests.insert_user(2, 'ALTERNATIVE-USER2')

    # Add two demo machines
    DB().query("INSERT INTO machines (id, description) VALUES(100, 'Machine 100')")
    DB().query("INSERT INTO machines (id, description) VALUES(101, 'Machine 101')")

    # Add 7 runs on different machines and dates
    DB().query("INSERT INTO runs(id, uri, branch, filename, machine_id, user_id, created_at) VALUES('00000000-0000-0000-0000-000000000000','-', '-', '-', 100, 2, NOW())")
    DB().query("INSERT INTO runs(id, uri, branch, filename, machine_id, user_id, created_at) VALUES('00000000-0000-0000-0000-000000000001','-', '-', '-', 100, 2, NOW())")
    DB().query("INSERT INTO runs(id, uri, branch, filename, machine_id, user_id, created_at) VALUES('00000000-0000-0000-0000-000000000002','-', '-', '-', 100, 2, NOW())")
    DB().query("INSERT INTO runs(id, uri, branch, filename, machine_id, user_id, created_at) VALUES('00000000-0000-0000-0000-000000000003','-', '-', '-', 100, 2, NOW())")

    DB().query("INSERT INTO runs(id, uri, branch, filename, machine_id, user_id, created_at) VALUES('00000000-0000-0000-0000-000000000004','-', '-', '-', 100, 2, NOW() + INTERVAL '1 DAY')")
    DB().query("INSERT INTO runs(id, uri, branch, filename, machine_id, user_id, created_at) VALUES('00000000-0000-0000-0000-000000000005','-', '-', '-', 100, 2, NOW() + INTERVAL '1 DAY')")

    DB().query("INSERT INTO runs(id, uri, branch, filename, machine_id, user_id, created_at) VALUES('00000000-0000-0000-0000-000000000006','-', '-', '-', 100, 345, NOW())")
    DB().query("INSERT INTO runs(id, uri, branch, filename, machine_id, user_id, created_at) VALUES('00000000-0000-0000-0000-000000000007','-', '-', '-', 100, 345, NOW())")

    DB().query("INSERT INTO runs(id, uri, branch, filename, machine_id, user_id, created_at) VALUES('00000000-0000-0000-0000-000000000008','-', '-', '-', 101, 345, NOW())")

    ## Add some fake metrics

    for i in range(0,9):
        DB().query('''INSERT INTO phase_stats(run_id, metric, detail_name, phase, value, type, unit, sampling_rate_avg, sampling_rate_max, sampling_rate_95p)
                    VALUES
                    (%s,'psu_energy_ac_mcp_machine','[MACHINE]','MY_CUSTOM_PHASE',5434523, 'TOTAL', 'uJ', 0, 0, 0)
        ''', params=(f"00000000-0000-0000-0000-00000000000{i}", ))
        DB().query('''INSERT INTO phase_stats(run_id, metric, detail_name, phase, value, type, unit, sampling_rate_avg, sampling_rate_max, sampling_rate_95p)
                    VALUES
                    (%s,'embodied_carbon_share_machine','[MACHINE]','MY_CUSTOM_PHASE',14610, 'TOTAL', 'ug', 0, 0, 0)
        ''', params=(f"00000000-0000-0000-0000-00000000000{i}", ))

    # Add another phase just for testing purposes is group works correctly
    DB().query('''INSERT INTO phase_stats(run_id, metric, detail_name, phase, value, type, unit, sampling_rate_avg, sampling_rate_max, sampling_rate_95p)
                VALUES
                (%s,'other_carbon_share_machine','[MACHINE]','001_[BASELINE]',14610, 'TOTAL', 'ug', 0, 0, 0)
    ''', params=('00000000-0000-0000-0000-000000000004', ))

    DB().query('''INSERT INTO phase_stats(run_id, metric, detail_name, phase, value, type, unit, sampling_rate_avg, sampling_rate_max, sampling_rate_95p)
                VALUES
                (%s,'another_carbon_share_machine','[MACHINE]','001_[BASELINE]',14610, 'TOTAL', 'ug', 0, 0, 0)
    ''', params=('00000000-0000-0000-0000-000000000004', ))

    DB().query('''INSERT INTO phase_stats(run_id, metric, detail_name, phase, value, type, unit, sampling_rate_avg, sampling_rate_max, sampling_rate_95p)
                VALUES
                (%s,'other_energy_share_machine','[MACHINE]','MY_CUSTOM_PHASE',5434523123, 'TOTAL', 'uJ', 0, 0, 0)
    ''', params=('00000000-0000-0000-0000-000000000004', ))

    assert DB().fetch_one('SELECT COUNT(id) FROM phase_stats')[0] == AMOUNT_OF_GMT_RUNS*2+3, 'Unexpected amount of row. Maybe demo data present?'


    copy_over_scenario_runner()

    assert DB().fetch_one('SELECT COUNT(id) FROM carbondb_data_raw')[0] == AMOUNT_OF_GMT_RUNS, 'LEFT JOIN expanded the rows! Should be no more than 10'

    for j in range(2,5):
        copy_over_scenario_runner()

    assert DB().fetch_one('SELECT COUNT(id) FROM carbondb_data_raw')[0] == AMOUNT_OF_GMT_RUNS * j, 'Copy did not results in identical rows'

    remove_duplicates()

    assert DB().fetch_one('SELECT COUNT(id) FROM carbondb_data_raw')[0] == AMOUNT_OF_GMT_RUNS, 'Remove duplicates did not remove identical rows'


    data = DB().fetch_one("SELECT id, source, type, machine, project FROM carbondb_data_raw WHERE user_id = 345 AND machine = 'Machine 101'", fetch_mode='dict')

    assert data['type'] == 'machine.server'
    assert data['machine'] == 'Machine 101'
    assert data['source'] == 'ScenarioRunner'
    assert data['project'] == 'ScenarioRunner'

    compress_carbondb_raw()

    assert DB().fetch_one('SELECT COUNT(id) FROM carbondb_data_raw')[0] == AMOUNT_OF_GMT_RUNS, 'Compress mingled with raw data. This should not happen'

    assert DB().fetch_one('SELECT COUNT(id) FROM carbondb_data')[0] == 4, 'Row compression resulted in more / less than 4 rows.'



    record_count = 4
    energy = 5434523*record_count / FROM_UJ_TO_J / FROM_J_TO_KWH # value initially was in uJ
    carbon = 14610*record_count / FROM_UG_TO_KG
    data = DB().fetch_one('SELECT energy_kwh_sum, carbon_kg_sum, carbon_intensity_g_avg, record_count FROM carbondb_data WHERE date = CURRENT_DATE AND user_id = 2', fetch_mode='dict')

    assert data['record_count'] == record_count
    assert math.isclose(data['energy_kwh_sum'], energy, rel_tol=1e-6)
    assert math.isclose(data['carbon_kg_sum'], carbon, rel_tol=1e-6)


    record_count = 2
    energy = 5434523*record_count / FROM_UJ_TO_J / FROM_J_TO_KWH # value initially was in uJ
    energy += 5434523123 / FROM_UJ_TO_J / FROM_J_TO_KWH  # other_energy_share_machine - in uJ

    carbon = 14610*record_count / FROM_UG_TO_KG
    carbon += 14610 / FROM_UG_TO_KG # other_carbon_share_machine
    carbon += 14610 / FROM_UG_TO_KG # another_carbon_share_machine
    data = DB().fetch_one("SELECT energy_kwh_sum, carbon_kg_sum, carbon_intensity_g_avg, record_count FROM carbondb_data WHERE date = CURRENT_DATE + INTERVAL '1 DAY' AND user_id = 2", fetch_mode='dict')

    assert data['record_count'] == record_count
    assert math.isclose(data['energy_kwh_sum'], energy, rel_tol=1e-6)
    assert math.isclose(data['carbon_kg_sum'], carbon, rel_tol=1e-6)


    record_count = 2
    energy = 5434523*record_count / FROM_UJ_TO_J / FROM_J_TO_KWH # value initially was in uJ

    carbon = 14610*record_count / FROM_UG_TO_KG
    machine_100_filter_id = DB().fetch_one("SELECT id FROM carbondb_machines WHERE 345 = ANY(user_ids) AND machine = 'Machine 100'")[0]
    data = DB().fetch_one("SELECT energy_kwh_sum, carbon_kg_sum, carbon_intensity_g_avg, record_count FROM carbondb_data WHERE user_id = 345 AND machine = %s", params=(machine_100_filter_id, ), fetch_mode='dict')

    assert data['record_count'] == record_count
    assert math.isclose(data['energy_kwh_sum'], energy, rel_tol=1e-6)
    assert math.isclose(data['carbon_kg_sum'], carbon, rel_tol=1e-6)



    record_count = 1
    energy = 5434523*record_count / FROM_UJ_TO_J / FROM_J_TO_KWH # value initially was in uJ

    carbon = 14610*record_count / FROM_UG_TO_KG
    machine_101_filter_id = DB().fetch_one("SELECT id FROM carbondb_machines WHERE 345 = ANY(user_ids)  AND machine = 'Machine 101'")[0]
    data = DB().fetch_one("SELECT energy_kwh_sum, carbon_kg_sum, carbon_intensity_g_avg, record_count FROM carbondb_data WHERE user_id = 345 AND machine = %s", params=(machine_101_filter_id, ),  fetch_mode='dict')

    assert data['record_count'] == record_count
    assert math.isclose(data['energy_kwh_sum'], energy, rel_tol=1e-6)
    assert math.isclose(data['carbon_kg_sum'], carbon, rel_tol=1e-6)



def test_big_values():

    energy_data = ENERGY_DATA.copy()
    energy_data['carbon_intensity_g'] = 200
    energy_data['energy_uj'] = 12741278312

    RANGE_AMOUNT=5_000

    for _ in range(RANGE_AMOUNT):

        response = requests.post(f"{API_URL}/v2/carbondb/add", json=energy_data, timeout=15)
        assert response.status_code == 202, Tests.assertion_info('success', response.text)

    compress_carbondb_raw()

    data = DB().fetch_one('SELECT * FROM carbondb_data WHERE date = CURRENT_DATE and user_id = 1', fetch_mode='dict')
    energy_kWh = (energy_data['energy_uj']*RANGE_AMOUNT)/(1_000_000*3_600*1_000)
    assert math.isclose(data['energy_kwh_sum'], energy_kWh, rel_tol=1e-5)

    carbon_kg = (energy_kWh*energy_data['carbon_intensity_g'])/1_000
    assert math.isclose(data['carbon_kg_sum'], carbon_kg, rel_tol=1e-5)

    assert data['carbon_intensity_g_avg'] == energy_data['carbon_intensity_g']


def test_carbondb_filter_mapped_to_same_id():

    Tests.insert_user(345, 'ALTERNATIVE-USER-CARBONDB')
    response = requests.post(f"{API_URL}/v2/carbondb/add", json=ENERGY_DATA, timeout=15) # Insert ID 1
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    response = requests.post(f"{API_URL}/v2/carbondb/add", json=ENERGY_DATA, timeout=15, headers={'X-Authentication': 'ALTERNATIVE-USER-CARBONDB'}) # Insert ID 345
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    compress_carbondb_raw()

    # User 1 can see all users and tags, bc super user by default
    response = requests.get(f"{API_URL}/v2/carbondb/filters", timeout=15) # ID 1
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert response.text == '{"success":true,"data":{"types":{"1":"machine.ci"},"tags":{"1":"cool","2":"mystery"},"machines":{"1":"my-machine"},"projects":{"1":"my-project"},"sources":{"1":"CUSTOM"},"users":{"0":"[GMT-SYSTEM]","1":"DEFAULT","345":"ALTERNATIVE-USER-CARBONDB"}}}'

    # User 345 can only see own tags
    response = requests.get(f"{API_URL}/v2/carbondb/filters", timeout=15, headers={'X-Authentication': 'ALTERNATIVE-USER-CARBONDB'}) # ID 345
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert response.text == '{"success":true,"data":{"types":{"1":"machine.ci"},"tags":{"1":"cool","2":"mystery"},"machines":{"1":"my-machine"},"projects":{"1":"my-project"},"sources":{"1":"CUSTOM"},"users":{"345":"ALTERNATIVE-USER-CARBONDB"}}}'

    # Tag is mapped to two users
    types = DB().fetch_all('SELECT user_ids FROM carbondb_types WHERE type = %s', params=(ENERGY_DATA['type'],))
    assert len(types) == 1
    assert types[0][0] == [1,345]

    # now we add a new type, only for user 1
    exp_data = ENERGY_DATA.copy()
    exp_data['type'] = 'asdasd' # this must map to the same tag ID later, but no other tags should be visible
    response = requests.post(f"{API_URL}/v2/carbondb/add", json=exp_data, timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    compress_carbondb_raw()

    # Tag is mapped to only one users
    types = DB().fetch_all('SELECT user_ids FROM carbondb_types WHERE type = %s', params=(exp_data['type'],))
    assert len(types) == 1
    assert types[0][0] == [1]

    # visible for user 1
    response = requests.get(f"{API_URL}/v2/carbondb/filters", timeout=15) # ID 1
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert response.text == '{"success":true,"data":{"types":{"1":"machine.ci","2":"asdasd"},"tags":{"1":"cool","2":"mystery"},"machines":{"1":"my-machine"},"projects":{"1":"my-project"},"sources":{"1":"CUSTOM"},"users":{"0":"[GMT-SYSTEM]","1":"DEFAULT","345":"ALTERNATIVE-USER-CARBONDB"}}}'


    # Not visible for alternative user
    response = requests.get(f"{API_URL}/v2/carbondb/filters", timeout=15, headers={'X-Authentication': 'ALTERNATIVE-USER-CARBONDB'}) # ID 345
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    assert response.text == '{"success":true,"data":{"types":{"1":"machine.ci"},"tags":{"1":"cool","2":"mystery"},"machines":{"1":"my-machine"},"projects":{"1":"my-project"},"sources":{"1":"CUSTOM"},"users":{"345":"ALTERNATIVE-USER-CARBONDB"}}}'
