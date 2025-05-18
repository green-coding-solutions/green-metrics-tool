import os
import io

GMT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))+'/../../'

import pytest
from contextlib import redirect_stdout, redirect_stderr

from tests import test_functions as Tests
from lib.db import DB
from lib.phase_stats import build_and_store_phase_stats
from lib.scenario_runner import ScenarioRunner

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
    assert data[0]['sampling_rate_avg'] is None, 'AVG sampling rate not in expected range'
    assert data[0]['sampling_rate_max'] is None, 'MAX sampling rate not in expected range'
    assert data[0]['sampling_rate_95p'] is None, '95p sampling rate not in expected range'


    assert data[1]['metric'] == 'psu_energy_ac_mcp_machine'
    assert data[1]['detail_name'] == '[MACHINE]'
    assert data[1]['unit'] == 'uJ'
    assert data[1]['value'] == 13177695386
    assert data[1]['type'] == 'TOTAL'
    assert data[1]['sampling_rate_avg'] == 101674, 'AVG sampling rate not in expected range'
    assert data[1]['sampling_rate_max'] == 107613, 'MAX sampling rate not in expected range'
    assert data[1]['sampling_rate_95p'] == 104671, '95p sampling rate not in expected range'
    assert isinstance(data[1]['sampling_rate_95p'], int)

    assert data[2]['metric'] == 'psu_power_ac_mcp_machine'
    assert data[2]['detail_name'] == '[MACHINE]'
    assert data[2]['unit'] == 'mW'
    assert data[2]['value'] == 28038
    assert data[2]['type'] == 'MEAN'
    assert data[2]['sampling_rate_avg'] == 101674, 'AVG sampling rate not in expected range'
    assert data[2]['sampling_rate_max'] == 107613, 'MAX sampling rate not in expected range'
    assert data[2]['sampling_rate_95p'] == 104671, '95p sampling rate not in expected range'
    assert isinstance(data[2]['sampling_rate_95p'], int)

def test_phase_stats_single_container():
    run_id = Tests.insert_run()
    Tests.import_cpu_utilization_container(run_id)

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
    Tests.import_cpu_utilization_container(run_id)
    Tests.import_cpu_energy(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, phase FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 7
    assert data[0]['metric'] == 'cpu_energy_rapl_msr_component'
    assert data[0]['phase'] == '004_[RUNTIME]'
    assert data[0]['value'] == 5495149000
    assert data[0]['type'] == 'TOTAL'
    assert data[0]['unit'] == 'uJ'
    assert data[0]['detail_name'] == 'Package_0'
    assert data[0]['sampling_rate_avg'] == 99217, 'AVG sampling rate not in expected range'
    assert data[0]['sampling_rate_max'] == 107827, 'MAX sampling rate not in expected range'
    assert data[0]['sampling_rate_95p'] ==  99486, '95p sampling rate not in expected range'

    assert data[3]['metric'] == 'cpu_power_rapl_msr_component'
    assert data[3]['phase'] == '004_[RUNTIME]'
    assert data[3]['value'] == 11692
    assert data[3]['type'] == 'MEAN'
    assert data[3]['unit'] == 'mW'
    assert data[3]['detail_name'] == 'Package_0'
    assert data[3]['sampling_rate_avg'] == 99217, 'AVG sampling rate not in expected range'
    assert data[3]['sampling_rate_max'] == 107827, 'MAX sampling rate not in expected range'
    assert data[3]['sampling_rate_95p'] ==  99486, '95p sampling rate not in expected range'

    assert data[4]['metric'] == 'cpu_utilization_cgroup_container'
    assert data[4]['phase'] == '004_[RUNTIME]'
    assert data[4]['value'] == 1983
    assert data[4]['type'] == 'MEAN'
    assert data[4]['unit'] == 'Ratio'
    assert data[4]['detail_name'] == 'Arne'
    assert data[4]['sampling_rate_avg'] == 99374, 'AVG sampling rate not in expected range'
    assert data[4]['sampling_rate_max'] == 100688, 'MAX sampling rate not in expected range'
    assert data[4]['sampling_rate_95p'] ==  99696, '95p sampling rate not in expected range'

    assert data[5]['metric'] == 'cpu_utilization_cgroup_container'
    assert data[5]['phase'] == '004_[RUNTIME]'
    assert data[5]['value'] == 3954
    assert data[5]['type'] == 'MEAN'
    assert data[5]['unit'] == 'Ratio'
    assert data[5]['detail_name'] == 'Not-Arne'
    assert data[5]['sampling_rate_avg'] == 99374, 'AVG sampling rate not in expected range'
    assert data[5]['sampling_rate_max'] == 100688, 'MAX sampling rate not in expected range'
    assert data[5]['sampling_rate_95p'] ==  99696, '95p sampling rate not in expected range'

def test_phase_embodied_and_operational_carbon():
    run_id = Tests.insert_run()
    Tests.import_machine_energy(run_id)

    sci = {"I":436,"R":0,"EL":4,"RS":1,"TE":181000,"R_d":"page request"}
    build_and_store_phase_stats(run_id, sci=sci)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, phase FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 5
    psu_energy_ac_mcp_machine = data[3]
    assert psu_energy_ac_mcp_machine['metric'] == 'psu_energy_ac_mcp_machine'

    psu_carbon_ac_mcp_machine = data[2]

    assert psu_carbon_ac_mcp_machine['metric'] == 'psu_carbon_ac_mcp_machine'
    assert psu_carbon_ac_mcp_machine['detail_name'] == '[MACHINE]'
    assert psu_carbon_ac_mcp_machine['unit'] == 'ug'

    operational_carbon_expected = int(psu_energy_ac_mcp_machine['value'] * MICROJOULES_TO_KWH * sci['I'] * 1_000_000)
    assert psu_carbon_ac_mcp_machine['value'] == operational_carbon_expected
    assert psu_carbon_ac_mcp_machine['type'] == 'TOTAL'

    phase_time_in_years = Tests.TEST_MEASUREMENT_DURATION_S / (60 * 60 * 24 * 365)
    embodied_carbon_expected = int((phase_time_in_years / sci['EL']) * sci['TE'] * sci['RS'] * 1_000_000)

    embodied_carbon_share_machine = data[0]
    assert embodied_carbon_share_machine['metric'] == 'embodied_carbon_share_machine'
    assert embodied_carbon_share_machine['detail_name'] == '[SYSTEM]'
    assert embodied_carbon_share_machine['unit'] == 'ug'
    assert embodied_carbon_share_machine['value'] == embodied_carbon_expected
    assert embodied_carbon_share_machine['type'] == 'TOTAL'

    assert embodied_carbon_share_machine['sampling_rate_avg'] is None, 'AVG sampling rate not in expected range'
    assert embodied_carbon_share_machine['sampling_rate_max'] is None, 'MAX sampling rate not in expected range'
    assert embodied_carbon_share_machine['sampling_rate_95p'] is None, '95p sampling rate not in expected range'

def test_phase_stats_energy_one_measurement():
    run_id = Tests.insert_run()
    Tests.import_single_cpu_energy_measurement(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 3
    assert data[1]['metric'] == 'phase_time_syscall_system'
    assert data[1]['detail_name'] == '[SYSTEM]'
    assert data[1]['value'] == 470000000
    assert data[1]['sampling_rate_95p'] is None

    assert data[0]['metric'] == 'cpu_energy_rapl_msr_component'
    assert data[0]['detail_name'] == 'Package_0'
    assert data[0]['value'] == 412000
    assert data[0]['sampling_rate_95p'] is None


def test_phase_stats_network_io_one_measurement():
    run_id = Tests.insert_run()

    with pytest.raises(RuntimeError) as e:
        Tests.import_single_network_io_procfs_measurement(run_id)
    assert str(e.value) == 'Metrics provider network_io_procfs_system seems to have not produced any measurements. Metrics log file was empty. Either consider having a higher sample rate or turn off provider.'


def test_phase_stats_network_io_two_measurements():
    run_id = Tests.insert_run()
    Tests.import_two_network_io_procfs_measurements(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 5
    assert data[2]['metric'] == 'phase_time_syscall_system'
    assert data[2]['detail_name'] == '[SYSTEM]'
    assert data[2]['value'] == 470000000
    assert data[2]['sampling_rate_95p'] is None

    assert data[3]['metric'] == 'network_io_procfs_system'
    assert data[3]['detail_name'] == 'CURRENT_ACTUAL_NETWORK_INTERFACE'
    assert data[3]['value'] == 13679
    assert data[3]['sampling_rate_95p'] == 1000486

def test_phase_stats_network_io_two_measurements_at_phase_border():
    run_id = Tests.insert_run()
    Tests.import_two_network_io_procfs_measurements_at_phase_border(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 5
    assert data[2]['metric'] == 'phase_time_syscall_system'
    assert data[2]['detail_name'] == '[SYSTEM]'
    assert data[2]['value'] == 470000000
    assert data[2]['sampling_rate_95p'] is None

    assert data[3]['metric'] == 'network_io_procfs_system'
    assert data[3]['detail_name'] == 'CURRENT_ACTUAL_NETWORK_INTERFACE'
    assert data[3]['value'] == 13686
    assert data[3]['sampling_rate_95p'] == 1000000
    assert data[3]['sampling_rate_avg'] == 1000000
    assert data[3]['sampling_rate_max'] == 1000000

    assert data[0]['metric'] == 'network_total_procfs_system'
    assert data[0]['detail_name'] == 'CURRENT_ACTUAL_NETWORK_INTERFACE'
    assert data[0]['value'] == 13686
    assert data[0]['sampling_rate_95p'] == 1000000
    assert data[0]['sampling_rate_avg'] == 1000000
    assert data[0]['sampling_rate_max'] == 1000000

    assert data[4]['metric'] == 'network_io_procfs_system'
    assert data[4]['detail_name'] == 'lo'
    assert data[4]['value'] == 0
    assert data[4]['sampling_rate_95p'] == 1000000
    assert data[4]['sampling_rate_avg'] == 1000000
    assert data[4]['sampling_rate_max'] == 1000000


def test_phase_stats_single_network_procfs():
    run_id = Tests.insert_run()
    Tests.import_network_io_procfs(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 23
    assert data[12]['metric'] == 'network_io_procfs_system'
    assert data[12]['detail_name'] == 'br-3d6ff3fb0904'
    assert data[12]['value'] == 649037
    assert data[12]['sampling_rate_avg'] == 99482, 'AVG sampling rate not in expected range'
    assert data[12]['sampling_rate_max'] == 105930, 'MAX sampling rate not in expected range'
    assert data[12]['sampling_rate_95p'] == 100488, '95p sampling rate not in expected range'
    assert isinstance(data[12]['sampling_rate_95p'], int)

    assert data[13]['metric'] == 'network_io_procfs_system'
    assert data[13]['detail_name'] == 'br-6062a8cb12d5'
    assert data[13]['value'] == 284

    assert data[13]['sampling_rate_avg'] == 99479, 'AVG sampling rate not in expected range'
    assert data[13]['sampling_rate_max'] == 105930, 'MAX sampling rate not in expected range'
    assert data[13]['sampling_rate_95p'] == 100477, '95p sampling rate not in expected range'
    assert isinstance(data[13]['sampling_rate_95p'], int)

    assert data[14]['metric'] == 'network_io_procfs_system'
    assert data[14]['detail_name'] == 'docker0'
    assert data[14]['value'] == 0

    assert data[14]['sampling_rate_avg'] == 99479, 'AVG sampling rate not in expected range'
    assert data[14]['sampling_rate_max'] == 105930, 'MAX sampling rate not in expected range'
    assert data[14]['sampling_rate_95p'] == 100477, '95p sampling rate not in expected range'
    assert isinstance(data[14]['sampling_rate_95p'], int)


def test_sci():
    runner = ScenarioRunner(uri=GMT_ROOT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/stress_sci.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=False, dev_no_phase_stats=False)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        run_id = runner.run()

    data = DB().fetch_all("SELECT value, unit FROM phase_stats WHERE phase = %s AND run_id = %s AND metric = 'software_carbon_intensity_global' ", params=('004_[RUNTIME]', run_id), fetch_mode='dict')


    assert len(data) == 1
    assert 50 < data[0]['value'] < 150
    assert data[0]['unit'] == 'ugCO2e/Cool run'
