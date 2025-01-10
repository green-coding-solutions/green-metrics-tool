import os

GMT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))+'/../../'

from tests import test_functions as Tests
from lib.db import DB
from lib.phase_stats import build_and_store_phase_stats

MICROJOULES_TO_KWH = 1/(3_600*1_000_000_000)

def test_phase_stats_single_energy():
    run_id = Tests.insert_run()
    Tests.import_machine_energy(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 3
    assert data[0]['metric'] == 'phase_time_syscall_system'
    assert data[0]['detail_name'] == '[SYSTEM]'
    assert data[0]['unit'] == 'us'
    assert data[0]['value'] == Tests.TEST_MEASUREMENT_END_TIME - Tests.TEST_MEASUREMENT_START_TIME
    assert data[0]['type'] == 'TOTAL'
    assert data[0]['sampling_rate_avg'] == 0, 'AVG sampling rate not in expected range'
    assert data[0]['sampling_rate_max'] == 0, 'MAX sampling rate not in expected range'
    assert data[0]['sampling_rate_95p'] == 0, '95p sampling rate not in expected range'


    assert data[1]['metric'] == 'psu_energy_ac_mcp_machine'
    assert data[1]['detail_name'] == '[machine]'
    assert data[1]['unit'] == 'uJ'
    assert data[1]['value'] == 13177695386
    assert data[1]['type'] == 'TOTAL'
    assert data[1]['sampling_rate_avg'] == 101674, 'AVG sampling rate not in expected range'
    assert data[1]['sampling_rate_max'] == 107613, 'MAX sampling rate not in expected range'
    assert data[1]['sampling_rate_95p'] == 104671, '95p sampling rate not in expected range'
    assert isinstance(data[1]['sampling_rate_95p'], int)

    assert data[2]['metric'] == 'psu_power_ac_mcp_machine'
    assert data[2]['detail_name'] == '[machine]'
    assert data[2]['unit'] == 'mW'
    assert data[2]['value'] == 28038
    assert data[2]['type'] == 'MEAN'
    assert data[2]['sampling_rate_avg'] == 101674, 'AVG sampling rate not in expected range'
    assert data[2]['sampling_rate_max'] == 107613, 'MAX sampling rate not in expected range'
    assert data[2]['sampling_rate_95p'] == 104671, '95p sampling rate not in expected range'
    assert isinstance(data[2]['sampling_rate_95p'], int)

def test_phase_stats_single_cgroup():
    run_id = Tests.insert_run()
    Tests.import_cpu_utilization(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 3
    assert data[0]['metric'] == 'phase_time_syscall_system'
    assert data[0]['detail_name'] == '[SYSTEM]'
    assert data[0]['unit'] == 'us'
    assert data[0]['value'] == Tests.TEST_MEASUREMENT_END_TIME - Tests.TEST_MEASUREMENT_START_TIME
    assert data[0]['type'] == 'TOTAL'

    assert data[1]['sampling_rate_avg'] == 99374, 'AVG sampling rate not in expected range'
    assert data[1]['sampling_rate_max'] == 100688, 'MAX sampling rate not in expected range'
    assert data[1]['sampling_rate_95p'] == 99696, '95p sampling rate not in expected range'
    assert isinstance(data[1]['sampling_rate_95p'], int)

def test_phase_stats_multi():
    run_id = Tests.insert_run()
    Tests.import_machine_energy(run_id)
    Tests.import_cpu_utilization(run_id)
    Tests.import_cpu_energy(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, phase FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 7
    assert data[1]['metric'] == 'cpu_energy_rapl_msr_component'
    assert data[1]['phase'] == '004_[RUNTIME]'
    assert data[1]['value'] == 5495149000
    assert data[1]['type'] == 'TOTAL'
    assert data[1]['unit'] == 'uJ'
    assert data[1]['detail_name'] == 'Package_0'
    assert data[1]['sampling_rate_avg'] == 99217, 'AVG sampling rate not in expected range'
    assert data[1]['sampling_rate_max'] == 107827, 'MAX sampling rate not in expected range'
    assert data[1]['sampling_rate_95p'] ==  99486, '95p sampling rate not in expected range'

    assert data[2]['metric'] == 'cpu_power_rapl_msr_component'
    assert data[2]['phase'] == '004_[RUNTIME]'
    assert data[2]['value'] == 11692
    assert data[2]['type'] == 'MEAN'
    assert data[2]['unit'] == 'mW'
    assert data[2]['detail_name'] == 'Package_0'
    assert data[2]['sampling_rate_avg'] == 99217, 'AVG sampling rate not in expected range'
    assert data[2]['sampling_rate_max'] == 107827, 'MAX sampling rate not in expected range'
    assert data[2]['sampling_rate_95p'] ==  99486, '95p sampling rate not in expected range'

    assert data[3]['metric'] == 'cpu_utilization_cgroup_container'
    assert data[3]['phase'] == '004_[RUNTIME]'
    assert data[3]['value'] == 1983
    assert data[3]['type'] == 'MEAN'
    assert data[3]['unit'] == 'Ratio'
    assert data[3]['detail_name'] == 'Arne'
    assert data[3]['sampling_rate_avg'] == 99374, 'AVG sampling rate not in expected range'
    assert data[3]['sampling_rate_max'] == 100688, 'MAX sampling rate not in expected range'
    assert data[3]['sampling_rate_95p'] ==  99696, '95p sampling rate not in expected range'

    assert data[4]['metric'] == 'cpu_utilization_cgroup_container'
    assert data[4]['phase'] == '004_[RUNTIME]'
    assert data[4]['value'] == 3954
    assert data[4]['type'] == 'MEAN'
    assert data[4]['unit'] == 'Ratio'
    assert data[4]['detail_name'] == 'Not-Arne'
    assert data[3]['sampling_rate_avg'] == 99374, 'AVG sampling rate not in expected range'
    assert data[3]['sampling_rate_max'] == 100688, 'MAX sampling rate not in expected range'
    assert data[3]['sampling_rate_95p'] ==  99696, '95p sampling rate not in expected range'

def test_phase_embodied_and_operational_carbon():
    run_id = Tests.insert_run()
    Tests.import_machine_energy(run_id)

    sci = {"I":436,"R":0,"EL":4,"RS":1,"TE":181000,"R_d":"page request"}
    build_and_store_phase_stats(run_id, sci=sci)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, phase FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 5

    psu_energy_ac_mcp_machine = data[1]
    assert psu_energy_ac_mcp_machine['metric'] == 'psu_energy_ac_mcp_machine'

    psu_carbon_ac_mcp_machine = data[3]

    assert psu_carbon_ac_mcp_machine['metric'] == 'psu_carbon_ac_mcp_machine'
    assert psu_carbon_ac_mcp_machine['detail_name'] == '[machine]'
    assert psu_carbon_ac_mcp_machine['unit'] == 'ug'

    operational_carbon_expected = int(psu_energy_ac_mcp_machine['value'] * MICROJOULES_TO_KWH * sci['I'] * 1_000_000)
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

    assert embodied_carbon_share_machine['sampling_rate_avg'] == 0, 'AVG sampling rate not in expected range'
    assert embodied_carbon_share_machine['sampling_rate_max'] == 0, 'MAX sampling rate not in expected range'
    assert embodied_carbon_share_machine['sampling_rate_95p'] == 0, '95p sampling rate not in expected range'
    assert isinstance(embodied_carbon_share_machine['sampling_rate_avg'], int)

def wip_test_phase_stats_single_network_procfs():
    run_id = Tests.insert_run()
    Tests.import_network_io_procfs(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 23
    assert data[1]['metric'] == 'network_io_procfs_system'
    assert data[1]['detail_name'] == 'br-3d6ff3fb0904'
    assert data[1]['value'] == 649004
    assert data[1]['sampling_rate_avg'] == 99482, 'AVG sampling rate not in expected range'
    assert data[1]['sampling_rate_max'] == 105929, 'MAX sampling rate not in expected range'
    assert data[1]['sampling_rate_95p'] == 100488, '95p sampling rate not in expected range'
    assert isinstance(data[1]['sampling_rate_95p'], int)

    assert data[3]['metric'] == 'network_io_procfs_system'
    assert data[3]['detail_name'] == 'br-6062a8cb12d5'
    assert data[3]['value'] == 403

    assert data[3]['sampling_rate_avg'] == 99476, 'AVG sampling rate not in expected range'
    assert data[3]['sampling_rate_max'] == 105929, 'MAX sampling rate not in expected range'
    assert data[3]['sampling_rate_95p'] == 100465, '95p sampling rate not in expected range'
    assert isinstance(data[3]['sampling_rate_95p'], int)

    assert data[5]['metric'] == 'network_io_procfs_system'
    assert data[5]['detail_name'] == 'docker0'
    assert data[5]['value'] == 0

    assert data[5]['sampling_rate_avg'] == 99476, 'AVG sampling rate not in expected range'
    assert data[5]['sampling_rate_max'] == 105929, 'MAX sampling rate not in expected range'
    assert data[5]['sampling_rate_95p'] == 100465, '95p sampling rate not in expected range'
    assert isinstance(data[5]['sampling_rate_95p'], int)
