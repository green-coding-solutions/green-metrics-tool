import os

GMT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))+'/../../'

from tests import test_functions as Tests
from lib.db import DB
from lib.phase_stats import build_and_store_phase_stats

MILLIJOULES_TO_KWH = 2.77778e-10
MICROJOULES_TO_KWH = 2.77778e-13

def test_phase_stats_single():
    run_id = Tests.insert_run()
    Tests.import_machine_energy(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT * FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 3
    assert data[0]['metric'] == 'phase_time_syscall_system'
    assert data[0]['detail_name'] == '[SYSTEM]'
    assert data[0]['unit'] == 'us'
    assert data[0]['value'] == Tests.TEST_MEASUREMENT_END_TIME - Tests.TEST_MEASUREMENT_START_TIME
    assert data[0]['type'] == 'TOTAL'


    assert data[1]['metric'] == 'psu_energy_ac_mcp_machine'
    assert data[1]['detail_name'] == '[machine]'
    assert data[1]['unit'] == 'mJ'
    assert data[1]['value'] == 13175452
    assert data[1]['type'] == 'TOTAL'

    assert data[2]['metric'] == 'psu_power_ac_mcp_machine'
    assert data[2]['detail_name'] == '[machine]'
    assert data[2]['unit'] == 'mW'
    assert data[2]['value'] == 28033
    assert data[2]['type'] == 'MEAN'


def test_phase_stats_multi():
    run_id = Tests.insert_run()
    Tests.import_machine_energy(run_id)
    Tests.import_cpu_utilization(run_id)
    Tests.import_cpu_energy(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT * FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 7
    assert data[1]['metric'] == 'cpu_energy_rapl_msr_component'
    assert data[1]['phase'] == '004_[RUNTIME]'
    assert data[1]['value'] == 5495149
    assert data[1]['type'] == 'TOTAL'
    assert data[1]['unit'] == 'mJ'
    assert data[1]['detail_name'] == 'Package_0'

    assert data[2]['metric'] == 'cpu_power_rapl_msr_component'
    assert data[2]['phase'] == '004_[RUNTIME]'
    assert data[2]['value'] == 11692
    assert data[2]['type'] == 'MEAN'
    assert data[2]['unit'] == 'mW'
    assert data[2]['detail_name'] == 'Package_0'

    assert data[3]['metric'] == 'cpu_utilization_cgroup_container'
    assert data[3]['phase'] == '004_[RUNTIME]'
    assert data[3]['value'] == 1985
    assert data[3]['type'] == 'MEAN'
    assert data[3]['unit'] == 'Ratio'
    assert data[3]['detail_name'] == 'Arne'

    assert data[4]['metric'] == 'cpu_utilization_cgroup_container'
    assert data[4]['phase'] == '004_[RUNTIME]'
    assert data[4]['value'] == 3959
    assert data[4]['type'] == 'MEAN'
    assert data[4]['unit'] == 'Ratio'
    assert data[4]['detail_name'] == 'Not-Arne'

def test_phase_embodied_and_operational_carbon():
    run_id = Tests.insert_run()
    Tests.import_machine_energy(run_id)

    sci = {"I":436,"R":0,"EL":4,"RS":1,"TE":181000,"R_d":"page request"}
    build_and_store_phase_stats(run_id, sci=sci)

    data = DB().fetch_all("SELECT * FROM phase_stats WHERE phase = %s ", params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 5

    psu_energy_ac_mcp_machine = data[1]
    assert psu_energy_ac_mcp_machine['metric'] == 'psu_energy_ac_mcp_machine'

    psu_carbon_ac_mcp_machine = data[3]

    assert psu_carbon_ac_mcp_machine['metric'] == 'psu_carbon_ac_mcp_machine'
    assert psu_carbon_ac_mcp_machine['detail_name'] == '[machine]'
    assert psu_carbon_ac_mcp_machine['unit'] == 'ug'

    operational_carbon_expected = int(psu_energy_ac_mcp_machine['value'] * MILLIJOULES_TO_KWH * sci['I'] * 1_000_000)
    assert psu_carbon_ac_mcp_machine['value'] == operational_carbon_expected
    assert psu_carbon_ac_mcp_machine['type'] == 'TOTAL'

    phase_time_in_years = Tests.TEST_MEASUREMENT_DURATION_S / (60 * 60 * 24 * 365)
    embodied_carbon_expected = int((phase_time_in_years / sci['EL']) * sci['TE'] * sci['RS'] * 1_000_000)

    embodied_carbon_share_machine = data[4]
    assert embodied_carbon_share_machine['metric'] == 'embodied_carbon_share_machine'
    assert embodied_carbon_share_machine['detail_name'] == '[SYSTEM]'
    assert embodied_carbon_share_machine['unit'] == 'ug'
    assert embodied_carbon_share_machine['value'] == embodied_carbon_expected
    assert embodied_carbon_share_machine['type'] == 'TOTAL'
