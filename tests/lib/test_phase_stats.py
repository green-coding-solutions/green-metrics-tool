import os
import io
import math
from decimal import Decimal

GMT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))+'/../../'

import pytest
from contextlib import redirect_stdout, redirect_stderr

from tests import test_functions as Tests
from lib.db import DB
from lib.phase_stats import build_and_store_phase_stats
from lib.scenario_runner import ScenarioRunner

MICROJOULES_TO_KWH = 1/(3_600*1_000_000_000)

def test_phase_stats_single_energy():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    df = Tests.import_machine_energy(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 3
    assert data[0]['metric'] == 'phase_time_syscall_system'
    assert data[0]['detail_name'] == '[SYSTEM]'
    assert data[0]['unit'] == 'us'
    assert data[0]['value'] == Tests.TEST_MEASUREMENT_RUNTIME_DURATION_NON_HIDDEN
    assert data[0]['type'] == 'TOTAL'
    assert data[0]['sampling_rate_avg'] is None, 'AVG sampling rate not in expected range'
    assert data[0]['sampling_rate_max'] is None, 'MAX sampling rate not in expected range'
    assert data[0]['sampling_rate_95p'] is None, '95p sampling rate not in expected range'


    assert data[1]['metric'] == 'psu_energy_ac_mcp_machine'
    assert data[1]['detail_name'] == '[MACHINE]'
    assert data[1]['unit'] == 'uJ'
    assert data[1]['value'] == Tests.filter_df_runtime_subphase(df, hidden=False)['value'].sum()
    assert data[1]['type'] == 'TOTAL'
    assert data[1]['sampling_rate_avg'] == 99502, 'AVG sampling rate not in expected range' # hardcoded for now. due for refactor
    assert data[1]['sampling_rate_max'] == 101999, 'MAX sampling rate not in expected range' # hardcoded for now. due for refactor
    assert data[1]['sampling_rate_95p'] == 100183, '95p sampling rate not in expected range' # hardcoded for now. due for refactor
    assert isinstance(data[1]['sampling_rate_95p'], int)

    assert data[2]['metric'] == 'psu_power_ac_mcp_machine'
    assert data[2]['detail_name'] == '[MACHINE]'
    assert data[2]['unit'] == 'mW'
    assert data[2]['value'] == 8384758 # hardcoded bc it is not energy / divided by total_runtime but rather by the samples seen
    assert data[2]['type'] == 'MEAN'
    assert data[2]['sampling_rate_avg'] == 99502, 'AVG sampling rate not in expected range' # hardcoded for now. due for refactor
    assert data[2]['sampling_rate_max'] == 101999, 'MAX sampling rate not in expected range'  # hardcoded for now. due for refactor
    assert data[2]['sampling_rate_95p'] == 100183, '95p sampling rate not in expected range'  # hardcoded for now. due for refactor
    assert isinstance(data[2]['sampling_rate_95p'], int)

def test_phase_stats_single_container():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    Tests.import_cpu_utilization_container(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 3
    assert data[0]['metric'] == 'phase_time_syscall_system'
    assert data[0]['detail_name'] == '[SYSTEM]'
    assert data[0]['unit'] == 'us'
    assert data[0]['value'] == Tests.TEST_MEASUREMENT_RUNTIME_DURATION_NON_HIDDEN
    assert data[0]['type'] == 'TOTAL'

    assert data[1]['metric'] == 'cpu_utilization_cgroup_container'
    assert data[1]['sampling_rate_avg'] == 99956, 'AVG sampling rate not in expected range'
    assert data[1]['sampling_rate_max'] == 101708, 'MAX sampling rate not in expected range'
    assert data[1]['sampling_rate_95p'] == 100602, '95p sampling rate not in expected range'
    assert isinstance(data[1]['sampling_rate_95p'], int)


def test_phase_stats_sub_phase():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    df_cpu_energy = Tests.import_cpu_energy(run_id)
    df_cpu_utilization = Tests.import_cpu_utilization_container(run_id)


    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, phase FROM phase_stats WHERE phase LIKE %s ', params=('%Stress', ), fetch_mode='dict')

    assert len(data) == 5
    assert data[0]['metric'] == 'phase_time_syscall_system'
    assert data[0]['phase'] == '007_Stress'
    assert data[0]['value'] == Tests.TEST_MEASUREMENT_STRESS_SUBPHASE_DURATION
    assert data[0]['type'] == 'TOTAL'
    assert data[0]['unit'] == 'us'
    assert data[0]['detail_name'] == '[SYSTEM]'
    assert data[0]['sampling_rate_avg'] is None, 'AVG sampling rate not in expected range'
    assert data[0]['sampling_rate_max'] is None, 'MAX sampling rate not in expected range'
    assert data[0]['sampling_rate_95p'] is None, '95p sampling rate not in expected range'


    assert data[1]['metric'] == 'cpu_energy_rapl_msr_component'
    assert data[1]['phase'] == '007_Stress'
    assert data[1]['value'] == Tests.filter_df_runtime_subphase(df_cpu_energy, phase_name='Stress')['value'].sum()
    assert data[1]['type'] == 'TOTAL'
    assert data[1]['unit'] == 'uJ'
    assert data[1]['detail_name'] == 'Package_0'
    assert data[1]['sampling_rate_avg'] == 100105, 'AVG sampling rate not in expected range' # hardcoded for now ... try Tests.filter_df_runtime_subphase(df_cpu_energy)['time_diff'].mean() when refactoring
    assert data[1]['sampling_rate_max'] == 101764, 'MAX sampling rate not in expected range' # hardcoded for now ... try Tests.filter_df_runtime_subphase(df_cpu_energy)['time_diff'].mean() when refactoring
    assert data[1]['sampling_rate_95p'] == 101364, '95p sampling rate not in expected range' # hardcoded for now ... try Tests.filter_df_runtime_subphase(df_cpu_energy)['time_diff'].mean() when refactoring


    df = df_cpu_utilization.loc[df_cpu_utilization['detail_name'] == data[4]['detail_name']]
    df = Tests.filter_df_runtime_subphase(df, phase_name='Stress')
    df['weighted_value'] = df['value'] * df['time_diff']
    assert data[4]['metric'] == 'cpu_utilization_cgroup_container'
    assert data[4]['phase'] == '007_Stress'
    assert data[4]['value'] == round(df['weighted_value'].sum() / df['time_diff'].sum())
    assert data[4]['type'] == 'MEAN'
    assert data[4]['unit'] == 'Ratio'
    assert data[4]['detail_name'] == df_cpu_utilization['detail_name'].iloc[1]
    assert data[4]['sampling_rate_avg'] == 100413, 'AVG sampling rate not in expected range'
    assert data[4]['sampling_rate_max'] == 101708, 'MAX sampling rate not in expected range'
    assert data[4]['sampling_rate_95p'] == 101392, '95p sampling rate not in expected range'

    df = df_cpu_utilization.loc[df_cpu_utilization['detail_name'] == data[3]['detail_name']]
    df = Tests.filter_df_runtime_subphase(df, phase_name='Stress')
    df['weighted_value'] = df['value'] * df['time_diff']
    assert data[3]['metric'] == 'cpu_utilization_cgroup_container'
    assert data[3]['phase'] == '007_Stress'
    assert data[3]['value'] == round(df['weighted_value'].sum() / df['time_diff'].sum())
    assert data[3]['type'] == 'MEAN'
    assert data[3]['unit'] == 'Ratio'
    assert data[3]['detail_name'] == df_cpu_utilization['detail_name'].iloc[0]
    assert data[3]['sampling_rate_avg'] == 100413, 'AVG sampling rate not in expected range'
    assert data[3]['sampling_rate_max'] == 101708, 'MAX sampling rate not in expected range'
    assert data[3]['sampling_rate_95p'] == 101392, '95p sampling rate not in expected range'

def test_phase_stats_multi():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    df_machine_energy = Tests.import_machine_energy(run_id)
    df_cpu_energy = Tests.import_cpu_energy(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, phase FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 5
    assert data[1]['metric'] == 'cpu_energy_rapl_msr_component'
    assert data[1]['phase'] == '004_[RUNTIME]'
    assert data[1]['value'] == Tests.filter_df_runtime_subphase(df_cpu_energy, hidden=False)['value'].sum()
    assert data[1]['type'] == 'TOTAL'
    assert data[1]['unit'] == 'uJ'
    assert data[1]['detail_name'] == 'Package_0'
    assert data[1]['sampling_rate_avg'] == 99524, 'AVG sampling rate not in expected range'
    assert data[1]['sampling_rate_max'] == 101764, 'MAX sampling rate not in expected range'
    assert data[1]['sampling_rate_95p'] ==  100111, '95p sampling rate not in expected range'

    assert data[3]['metric'] == 'cpu_power_rapl_msr_component'
    assert data[3]['phase'] == '004_[RUNTIME]'
    assert data[3]['value'] == 4728 # hardcoded bc it is not energy / divided by total_runtime but rather by the samples seen
    assert data[3]['type'] == 'MEAN'
    assert data[3]['unit'] == 'mW'
    assert data[3]['detail_name'] == 'Package_0'
    assert data[3]['sampling_rate_avg'] == 99524, 'AVG sampling rate not in expected range' # hardcoded for now ... try Tests.filter_df_runtime_subphase(df_cpu_energy)['time_diff'].mean() when refactoring
    assert data[3]['sampling_rate_max'] == 101764, 'MAX sampling rate not in expected range' # hardcoded for now ... try Tests.filter_df_runtime_subphase(df_cpu_energy)['time_diff'].mean() when refactoring
    assert data[3]['sampling_rate_95p'] ==  100111, '95p sampling rate not in expected range' # hardcoded for now ... try Tests.filter_df_runtime_subphase(df_cpu_energy)['time_diff'].mean() when refactoring


    assert data[2]['metric'] == 'psu_energy_ac_mcp_machine'
    assert data[2]['phase'] == '004_[RUNTIME]'
    assert data[2]['value'] == Tests.filter_df_runtime_subphase(df_machine_energy, hidden=False)['value'].sum()
    assert data[2]['type'] == 'TOTAL'
    assert data[2]['unit'] == 'uJ'
    assert data[2]['detail_name'] == '[MACHINE]'
    assert data[2]['sampling_rate_avg'] == 99502, 'AVG sampling rate not in expected range' # hardcoded for now ... try Tests.filter_df_runtime_subphase(df_cpu_energy)['time_diff'].mean() when refactoring
    assert data[2]['sampling_rate_max'] == 101999, 'MAX sampling rate not in expected range' # hardcoded for now ... try Tests.filter_df_runtime_subphase(df_cpu_energy)['time_diff'].mean() when refactoring
    assert data[2]['sampling_rate_95p'] ==  100183, '95p sampling rate not in expected range' # hardcoded for now ... try Tests.filter_df_runtime_subphase(df_cpu_energy)['time_diff'].mean() when refactoring

    assert data[4]['metric'] == 'psu_power_ac_mcp_machine'
    assert data[4]['phase'] == '004_[RUNTIME]'
    assert data[4]['value'] == 8384758 # hardcoded bc it is not energy / divided by total_runtime but rather by the samples seen
    assert data[4]['type'] == 'MEAN'
    assert data[4]['unit'] == 'mW'
    assert data[4]['detail_name'] == '[MACHINE]'
    assert data[4]['sampling_rate_avg'] == 99502, 'AVG sampling rate not in expected range' # hardcoded for now ... try Tests.filter_df_runtime_subphase(df_cpu_energy)['time_diff'].mean() when refactoring
    assert data[4]['sampling_rate_max'] == 101999, 'MAX sampling rate not in expected range' # hardcoded for now ... try Tests.filter_df_runtime_subphase(df_cpu_energy)['time_diff'].mean() when refactoring
    assert data[4]['sampling_rate_95p'] ==  100183, '95p sampling rate not in expected range' # hardcoded for now ... try Tests.filter_df_runtime_subphase(df_cpu_energy)['time_diff'].mean() when refactoring


'''
    The weighted average is notoiously hard to replay, this we work here
    with only static values. Otherwise we need to re-create SQL functions, which kind if defys the use-case of a test to
    not introduce possilby errorneous code, but test against a ground truth
'''
def test_cpu_utilization_weighted_average_multi():

    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    df_cpu_utilization = Tests.import_cpu_utilization_container(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, phase FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')
    assert len(data) == 3


    df = df_cpu_utilization.loc[df_cpu_utilization['detail_name'] == data[2]['detail_name']]
    df = Tests.filter_df_runtime_subphase(df)

    assert data[2]['metric'] == 'cpu_utilization_cgroup_container'
    assert data[2]['phase'] == '004_[RUNTIME]'
    assert data[2]['value'] == 8
    assert data[2]['type'] == 'MEAN'
    assert data[2]['unit'] == 'Ratio'
    assert data[2]['detail_name'] == '939f410a21730a2275e91b8a949884f7f426b89e50e8b2ffceca271b6a4573b6'
    assert data[2]['sampling_rate_avg'] == 99956, 'AVG sampling rate not in expected range'
    assert data[2]['sampling_rate_max'] == 101708, 'MAX sampling rate not in expected range'
    assert data[2]['sampling_rate_95p'] ==  100602, '95p sampling rate not in expected range'

    assert data[1]['metric'] == 'cpu_utilization_cgroup_container'
    assert data[1]['phase'] == '004_[RUNTIME]'
    assert data[1]['value'] == 1285
    assert data[1]['type'] == 'MEAN'
    assert data[1]['unit'] == 'Ratio'
    assert data[1]['detail_name'] == '38d1e484f336c40a6e60e4518915a4e385f62fdddd47994d6adcb4fb294b2ec8'
    assert data[2]['sampling_rate_avg'] == 99956, 'AVG sampling rate not in expected range'
    assert data[2]['sampling_rate_max'] == 101708, 'MAX sampling rate not in expected range'
    assert data[2]['sampling_rate_95p'] ==  100602, '95p sampling rate not in expected range'


def test_phase_embodied_and_operational_carbon():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    Tests.import_machine_energy(run_id)

    sci = {"I":436,"R":0,"EL":4,"RS":1,"TE":181000,"R_d":"page request"}
    build_and_store_phase_stats(run_id, sci=sci)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, phase FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 5
    psu_energy_ac_mcp_machine = data[1]
    assert psu_energy_ac_mcp_machine['metric'] == 'psu_energy_ac_mcp_machine'

    psu_carbon_ac_mcp_machine = data[2]

    assert psu_carbon_ac_mcp_machine['metric'] == 'psu_carbon_ac_mcp_machine'
    assert psu_carbon_ac_mcp_machine['detail_name'] == '[MACHINE]'
    assert psu_carbon_ac_mcp_machine['unit'] == 'ug'

    operational_carbon_expected = int(psu_energy_ac_mcp_machine['value'] * MICROJOULES_TO_KWH * sci['I'] * 1_000_000)
    assert psu_carbon_ac_mcp_machine['value'] == operational_carbon_expected
    assert psu_carbon_ac_mcp_machine['type'] == 'TOTAL'

    phase_time_in_years = Tests.TEST_MEASUREMENT_RUNTIME_DURATION_NON_HIDDEN_S / (60 * 60 * 24 * 365)
    embodied_carbon_expected = int((phase_time_in_years / sci['EL']) * sci['TE'] * sci['RS'] * 1_000_000)

    embodied_carbon_share_machine = data[3]
    assert embodied_carbon_share_machine['metric'] == 'embodied_carbon_share_machine'
    assert embodied_carbon_share_machine['detail_name'] == '[SYSTEM]'
    assert embodied_carbon_share_machine['unit'] == 'ug'
    assert embodied_carbon_share_machine['value'] == embodied_carbon_expected
    assert embodied_carbon_share_machine['type'] == 'TOTAL'

    assert embodied_carbon_share_machine['sampling_rate_avg'] is None, 'AVG sampling rate not in expected range'
    assert embodied_carbon_share_machine['sampling_rate_max'] is None, 'MAX sampling rate not in expected range'
    assert embodied_carbon_share_machine['sampling_rate_95p'] is None, '95p sampling rate not in expected range'

def test_phase_stats_energy_one_measurement():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    df = Tests.import_cpu_energy(run_id, filename='cpu_energy_rapl_msr_component_single_measurement.log')

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 3
    assert data[1]['metric'] == 'phase_time_syscall_system'
    assert data[1]['detail_name'] == '[SYSTEM]'
    assert data[1]['value'] == Tests.TEST_MEASUREMENT_RUNTIME_DURATION_NON_HIDDEN
    assert data[1]['sampling_rate_95p'] is None

    assert data[0]['metric'] == 'cpu_energy_rapl_msr_component'
    assert data[0]['detail_name'] == 'Package_0'
    assert data[0]['value'] == Tests.filter_df_runtime_subphase(df, hidden=False)['value'].mean()
    assert data[0]['sampling_rate_95p'] is None

def test_phase_stats_hidden_energy():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    df = Tests.import_cpu_energy(run_id)

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase LIKE %s ', params=('%_Hidden warmup', ), fetch_mode='dict')

    assert len(data) == 3
    assert data[0]['metric'] == 'phase_time_syscall_system'
    assert data[0]['detail_name'] == '[SYSTEM]'
    assert data[0]['value'] == Tests.TEST_MEASUREMENT_HIDDEN_WARMUP_SUBPHASE_DURATION
    assert data[0]['sampling_rate_95p'] is None

    assert data[1]['metric'] == 'cpu_energy_rapl_msr_component'
    assert data[1]['detail_name'] == 'Package_0'
    assert data[1]['value'] == Tests.filter_df_runtime_subphase(df, phase_name='Hidden warmup')['value'].sum()
    assert data[1]['sampling_rate_95p'] == 99361


def test_phase_stats_network_io_one_measurement():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)

    with pytest.raises(RuntimeError) as e:
        Tests.import_network_io_procfs(run_id, filename='network_io_procfs_system_single_measurement.log')

    assert str(e.value) == 'Metrics provider network_io_procfs_system seems to have not produced any measurements. Metrics log file was empty. Either consider having a higher sample rate or turn off provider.'



def test_phase_stats_network_io_phase_border_in():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    df_network_io = Tests.import_network_io_procfs(run_id, filename='network_io_procfs_system_two_measurements_at_phase_border_in.log')

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 5
    assert data[2]['metric'] == 'phase_time_syscall_system'
    assert data[2]['detail_name'] == '[SYSTEM]'
    assert data[2]['value'] == Tests.TEST_MEASUREMENT_RUNTIME_DURATION_NON_HIDDEN
    assert data[2]['sampling_rate_95p'] is None

    assert data[0]['metric'] == 'network_total_procfs_system'
    assert data[0]['detail_name'] == 'CURRENT_ACTUAL_NETWORK_INTERFACE'
    assert data[0]['value'] == 100 # as seen in file network_io_procfs_system_two_measurements_at_phase_border.log
    assert data[0]['sampling_rate_95p'] is None
    assert data[0]['sampling_rate_avg'] is None
    assert data[0]['sampling_rate_max'] is None

    df = df_network_io.loc[df_network_io['detail_name'] == data[3]['detail_name']]
    assert data[3]['metric'] == 'network_io_procfs_system'
    assert data[3]['detail_name'] == 'CURRENT_ACTUAL_NETWORK_INTERFACE'
    assert data[3]['value'] == round(Tests.filter_df_runtime_subphase(df, hidden=False)['value'].sum()/Tests.TEST_MEASUREMENT_RUNTIME_DURATION_NON_HIDDEN * 1e6)
    assert data[3]['sampling_rate_95p'] is None
    assert data[3]['sampling_rate_avg'] is None
    assert data[3]['sampling_rate_max'] is None

def test_phase_stats_network_io_phase_border_out():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    Tests.import_network_io_procfs(run_id, filename='network_io_procfs_system_two_measurements_at_phase_border_out.log')

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 1
    assert data[0]['metric'] == 'phase_time_syscall_system'
    assert data[0]['detail_name'] == '[SYSTEM]'
    assert data[0]['value'] == Tests.TEST_MEASUREMENT_RUNTIME_DURATION_NON_HIDDEN
    assert data[0]['sampling_rate_95p'] is None

def test_phase_stats_network_io_in_hidden_phase():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    Tests.import_network_io_procfs(run_id, filename='network_io_procfs_system_in_hidden_phase.log')

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 1
    assert data[0]['metric'] == 'phase_time_syscall_system'
    assert data[0]['detail_name'] == '[SYSTEM]'
    assert data[0]['value'] == Tests.TEST_MEASUREMENT_RUNTIME_DURATION_NON_HIDDEN
    assert data[0]['sampling_rate_95p'] is None

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase LIKE %s ', params=('%_Hidden warmup', ), fetch_mode='dict')

    assert len(data) == 5
    assert data[0]['metric'] == 'phase_time_syscall_system'
    assert data[0]['detail_name'] == '[SYSTEM]'
    assert data[0]['value'] == Tests.TEST_MEASUREMENT_HIDDEN_WARMUP_SUBPHASE_DURATION
    assert data[0]['sampling_rate_95p'] is None

    assert data[2]['metric'] == 'network_total_procfs_system'
    assert data[2]['detail_name'] == 'CURRENT_ACTUAL_NETWORK_INTERFACE'
    assert data[2]['value'] == 200 # as seen in file network_io_procfs_system_in_hidden_phase.log
    assert data[2]['sampling_rate_95p'] == 99999


def test_phase_stats_network_procfs_manually_verifyable():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    df_network_io = Tests.import_network_io_procfs(run_id, filename='network_io_procfs_system_two_measurements.log')

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('008_Download', ), fetch_mode='dict')

    assert len(data) == 5

    assert data[0]['metric'] == 'phase_time_syscall_system'
    assert data[0]['detail_name'] == '[SYSTEM]'
    assert data[0]['unit'] == 'us'
    assert data[0]['value'] == Tests.TEST_MEASUREMENT_DOWNLOAD_SUBPHASE_DURATION
    assert data[0]['type'] == 'TOTAL'
    assert data[0]['sampling_rate_avg'] is None, 'AVG sampling rate not in expected range'
    assert data[0]['sampling_rate_max'] is None, 'MAX sampling rate not in expected range'
    assert data[0]['sampling_rate_95p'] is None, '95p sampling rate not in expected range'

    df = df_network_io.loc[df_network_io['detail_name'] == data[2]['detail_name']]
    assert data[2]['metric'] == 'network_total_procfs_system'
    assert data[2]['detail_name'] == 'CURRENT_ACTUAL_NETWORK_INTERFACE'
    assert data[2]['value'] == 3003 # hardcoded as readable in file
    assert data[2]['sampling_rate_avg'] == 100000, 'AVG sampling rate not in expected range' # we fixed it manually to 100000
    assert data[2]['sampling_rate_max'] == 100000, 'MAX sampling rate not in expected range'
    assert data[2]['sampling_rate_95p'] == 100000, '95p sampling rate not in expected range'
    assert isinstance(data[2]['sampling_rate_95p'], int)

    df = df_network_io.loc[df_network_io['detail_name'] == data[1]['detail_name']]
    assert data[1]['metric'] == 'network_io_procfs_system'
    assert data[1]['detail_name'] == 'CURRENT_ACTUAL_NETWORK_INTERFACE'
    assert data[1]['value'] == 10010
    assert data[1]['sampling_rate_avg'] == 100000, 'AVG sampling rate not in expected range' # we fixed it manually to 100000
    assert data[1]['sampling_rate_max'] == 100000, 'MAX sampling rate not in expected range'
    assert data[1]['sampling_rate_95p'] == 100000, '95p sampling rate not in expected range'
    assert isinstance(data[1]['sampling_rate_95p'], int)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 5

    assert data[0]['metric'] == 'phase_time_syscall_system'
    assert data[0]['detail_name'] == '[SYSTEM]'
    assert data[0]['unit'] == 'us'
    assert data[0]['value'] == Tests.TEST_MEASUREMENT_RUNTIME_DURATION_NON_HIDDEN
    assert data[0]['type'] == 'TOTAL'
    assert data[0]['sampling_rate_avg'] is None, 'AVG sampling rate not in expected range'
    assert data[0]['sampling_rate_max'] is None, 'MAX sampling rate not in expected range'
    assert data[0]['sampling_rate_95p'] is None, '95p sampling rate not in expected range'


    df = df_network_io.loc[df_network_io['detail_name'] == data[1]['detail_name']]
    assert data[1]['metric'] == 'network_total_procfs_system'
    assert data[1]['detail_name'] == 'CURRENT_ACTUAL_NETWORK_INTERFACE'
    assert data[1]['value'] == Tests.filter_df_runtime_subphase(df, hidden=False)['value'].sum()
    assert data[1]['sampling_rate_avg'] == 100000, 'AVG sampling rate not in expected range' # we fixed it manually to 100000
    assert data[1]['sampling_rate_max'] == 100000, 'MAX sampling rate not in expected range'
    assert data[1]['sampling_rate_95p'] == 100000, '95p sampling rate not in expected range'
    assert isinstance(data[1]['sampling_rate_95p'], int)

    df = df_network_io.loc[df_network_io['detail_name'] == data[3]['detail_name']]
    assert data[3]['metric'] == 'network_io_procfs_system'
    assert data[3]['detail_name'] == 'CURRENT_ACTUAL_NETWORK_INTERFACE'
    assert data[3]['value'] == 878
    assert data[3]['sampling_rate_avg'] == 100000, 'AVG sampling rate not in expected range' # we fixed it manually to 100000
    assert data[3]['sampling_rate_max'] == 100000, 'MAX sampling rate not in expected range'
    assert data[3]['sampling_rate_95p'] == 100000, '95p sampling rate not in expected range'
    assert isinstance(data[3]['sampling_rate_95p'], int)



def test_phase_stats_network_procfs():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    df_network_io = Tests.import_network_io_procfs(run_id, filename='network_io_procfs_system.log')

    build_and_store_phase_stats(run_id)

    data = DB().fetch_all('SELECT metric, detail_name, unit, value, type, sampling_rate_avg, sampling_rate_max, sampling_rate_95p FROM phase_stats WHERE phase = %s ', params=('004_[RUNTIME]', ), fetch_mode='dict')

    assert len(data) == 27

    df = df_network_io.loc[df_network_io['detail_name'] == data[13]['detail_name']]
    assert data[13]['metric'] == 'network_total_procfs_system'
    assert data[13]['detail_name'] == 'wlp170s0'
    assert data[13]['value'] == Tests.filter_df_runtime_subphase(df, hidden=False)['value'].sum()
    assert data[13]['sampling_rate_avg'] == 99771, 'AVG sampling rate not in expected range'
    assert data[13]['sampling_rate_max'] == 101780, 'MAX sampling rate not in expected range'
    assert data[13]['sampling_rate_95p'] == 100411, '95p sampling rate not in expected range'
    assert isinstance(data[13]['sampling_rate_95p'], int)

    df = df_network_io.loc[df_network_io['detail_name'] == data[2]['detail_name']]
    assert data[2]['metric'] == 'network_total_procfs_system'
    assert data[2]['detail_name'] == 'br-f1a25ccf9cd0'
    assert data[2]['value'] == Tests.filter_df_runtime_subphase(df, hidden=False)['value'].sum()


    df = df_network_io.loc[df_network_io['detail_name'] == data[16]['detail_name']]
    assert data[16]['metric'] == 'network_io_procfs_system'
    assert data[16]['detail_name'] == 'docker0'
    assert data[16]['value'] == round(Tests.filter_df_runtime_subphase(df, hidden=False)['value'].sum()/Tests.TEST_MEASUREMENT_RUNTIME_DURATION_NON_HIDDEN * 1e6)
    assert data[16]['sampling_rate_avg'] == 99771, 'AVG sampling rate not in expected range'
    assert data[16]['sampling_rate_max'] == 101780, 'MAX sampling rate not in expected range'
    assert data[16]['sampling_rate_95p'] == 100411, '95p sampling rate not in expected range'
    assert isinstance(data[16]['sampling_rate_95p'], int)


def test_phase_stats_network_data():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    Tests.import_network_io_cgroup_container(run_id)

    test_sci_config = {
        'N': 0.001,    # Network energy intensity (kWh/GB)
        'I': 500,      # Carbon intensity (gCO2e/kWh)
    }

    build_and_store_phase_stats(run_id, sci=test_sci_config)

    # Network energy data
    network_energy_data = DB().fetch_all(
        'SELECT metric, detail_name, unit, value, type, phase FROM phase_stats WHERE phase = %s AND metric = %s',
        params=('004_[RUNTIME]', 'network_energy_formula_global'), fetch_mode='dict'
    )

    assert len(network_energy_data) == 1, f"Expected 1 network energy formula entry, got {len(network_energy_data)}"

    network_energy_entry = network_energy_data[0]
    assert network_energy_entry['metric'] == 'network_energy_formula_global'
    assert network_energy_entry['detail_name'] == '[FORMULA]'
    assert network_energy_entry['unit'] == 'uJ'
    assert network_energy_entry['type'] == 'TOTAL'
    assert network_energy_entry['phase'] == '004_[RUNTIME]'

    network_totals = DB().fetch_all(
        'SELECT detail_name, value FROM phase_stats WHERE phase = %s AND metric = %s',
        params=('004_[RUNTIME]', 'network_total_cgroup_container'), fetch_mode='dict'
    )
    total_network_bytes = sum(row['value'] for row in network_totals)
    expected_network_energy_kwh = Decimal(total_network_bytes) / 1_000_000_000 * Decimal(test_sci_config['N'])
    expected_network_energy_uj = expected_network_energy_kwh * 3_600_000_000_000
    assert math.isclose(network_energy_entry['value'], expected_network_energy_uj, rel_tol=1e-5), f"Expected network energy: {expected_network_energy_uj}, got: {network_energy_entry['value']}"

    # Network carbon data
    network_carbon_data = DB().fetch_all(
        'SELECT metric, detail_name, unit, value, type FROM phase_stats WHERE phase = %s AND metric = %s',
        params=('004_[RUNTIME]', 'network_carbon_formula_global'), fetch_mode='dict'
    )

    assert len(network_carbon_data) == 1, "Expected 1 network carbon formula entry"

    network_carbon_entry = network_carbon_data[0]
    # expected_network_carbon_ug = expected_network_energy_kwh * Decimal(test_sci_config['I']) * 1_000_000 # not used ATM. See below

    assert network_carbon_entry['metric'] == 'network_carbon_formula_global'
    assert network_carbon_entry['detail_name'] == '[FORMULA]'
    assert network_carbon_entry['unit'] == 'ug'
    assert network_carbon_entry['type'] == 'TOTAL'
    assert network_carbon_entry['value'] == 6 # due to multiple rounding steps the current data actually gives 7 when calculated directly, but the rounding gets it down to 6

def test_sci_calculation():
    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    Tests.import_machine_energy(run_id)  # Machine energy component
    Tests.import_network_io_cgroup_container(run_id)  # Network component (custom N parameter)

    # Define comprehensive SCI configuration with all required parameters
    test_sci_config = {
        'N': 0.001,    # Network energy intensity (kWh/GB)
        'I': 500,      # Carbon intensity (gCO2e/kWh)
        'EL': 4,       # Expected lifespan (years)
        'TE': 300000,  # Total embodied emissions (gCO2e)
        'RS': 1,       # Resource share (100%)
        'R': 10,       # Functional unit count (10 runs)
        'R_d': 'test runs'  # Functional unit description
    }

    build_and_store_phase_stats(run_id, sci=test_sci_config)

    # Verify all SCI components are calculated and stored correctly

    psu_energy_ac_mcp_machine = DB().fetch_all(
        'SELECT metric, value, unit FROM phase_stats WHERE phase = %s AND metric = %s',
        params=('004_[RUNTIME]', 'psu_energy_ac_mcp_machine'), fetch_mode='dict'
    )
    assert len(psu_energy_ac_mcp_machine) == 1, "Machine energy should be calculated"

    # 1. Machine carbon from energy consumption
    machine_carbon_data = DB().fetch_all(
        'SELECT metric, value, unit FROM phase_stats WHERE phase = %s AND metric = %s',
        params=('004_[RUNTIME]', 'psu_carbon_ac_mcp_machine'), fetch_mode='dict'
    )
    assert len(machine_carbon_data) == 1, "Machine carbon should be calculated"
    machine_carbon_ug = machine_carbon_data[0]['value']
    operational_carbon_expected = int(psu_energy_ac_mcp_machine[0]['value'] * MICROJOULES_TO_KWH * test_sci_config['I'] * 1_000_000)
    assert operational_carbon_expected == machine_carbon_ug

    # 2. Embodied carbon calculation
    embodied_carbon_data = DB().fetch_all(
        'SELECT metric, value, unit FROM phase_stats WHERE phase = %s AND metric = %s',
        params=('004_[RUNTIME]', 'embodied_carbon_share_machine'), fetch_mode='dict'
    )
    assert len(embodied_carbon_data) == 1, "Embodied carbon should be calculated"
    embodied_carbon_ug = embodied_carbon_data[0]['value']

    # 3. Final SCI calculation verification
    sci_data = DB().fetch_all(
        'SELECT value, unit FROM phase_stats WHERE phase = %s AND metric = %s',
        params=('004_[RUNTIME]', 'software_carbon_intensity_global'), fetch_mode='dict'
    )
    assert len(sci_data) == 1, "SCI should be calculated for the whole run"
    sci_entry = sci_data[0]

    # Verify SCI unit format includes functional unit description - fail if other unit occurs
    expected_unit = f"ugCO2e/{test_sci_config['R_d']}"
    assert sci_entry['unit'] == expected_unit, \
        f"Test fails: Unexpected unit detected. Expected: {expected_unit}, got: {sci_entry['unit']}. This test is designed to fail when incorrect units are present."

    # Verify SCI value matches expected value: (machine_carbon + embodied_carbon) / R
    expected_sci_value = (machine_carbon_ug + embodied_carbon_ug) / Decimal(test_sci_config['R'])
    assert math.isclose(abs(sci_entry['value']), expected_sci_value, rel_tol=1e-5), f"SCI calculation should be correct. Expected: {expected_sci_value}, got: {sci_entry['value']}"

    # Verify SCI value is reasonable (positive and within expected range)
    assert sci_entry['value'] > 0, "SCI should be positive"
    assert sci_entry['value'] < 1000000, "SCI should be reasonable (less than 1M ugCO2e per functional unit)"

def test_sci_run():
    runner = ScenarioRunner(uri=GMT_ROOT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/stress_sci.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=False, dev_no_phase_stats=False)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        run_id = runner.run()

    data = DB().fetch_all("SELECT value, unit FROM phase_stats WHERE phase = %s AND run_id = %s AND metric = 'software_carbon_intensity_global' ", params=('004_[RUNTIME]', run_id), fetch_mode='dict')

    assert len(data) == 1
    assert 50 < data[0]['value'] < 150
    assert data[0]['unit'] == 'ugCO2e/Cool run'

def test_sci_multi_steps_run():
    runner = ScenarioRunner(uri=GMT_ROOT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/stress_sci_multi.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=False, dev_no_phase_stats=False)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        run_id = runner.run()

    data = DB().fetch_all("SELECT value, unit FROM phase_stats WHERE phase = %s AND run_id = %s AND metric = 'software_carbon_intensity_global' ", params=('004_[RUNTIME]', run_id), fetch_mode='dict')

    assert len(data) == 1
    assert 8 < data[0]['value'] < 20
    assert data[0]['unit'] == 'ugCO2e/Cool run'
