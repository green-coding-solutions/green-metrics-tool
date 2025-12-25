import os
import tempfile
import psutil
import subprocess

GMT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))+'/../../'

import pytest
from tests import test_functions as Tests
from lib.db import DB
from lib.global_config import GlobalConfig

from lib import utils
from lib import resource_limits
from lib.scenario_runner import ScenarioRunner
from metric_providers.network.io.procfs.system.provider import NetworkIoProcfsSystemProvider

#pylint: disable=unused-argument
@pytest.fixture(autouse=True, scope='module') # override by setting scope to module only
def setup_and_cleanup_test():
    GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/../test-config.yml") # we want to do this globally for all tests
    yield
    Tests.reset_db()

run_id = None
MB = 1000*1000 # Note: GMT uses SI Units!
MICROSECONDS = 1_000_000

# Runs once per file before any test(
#pylint: disable=expression-not-assigned
def setup_module(module):
    global run_id #pylint: disable=global-statement

    runner = ScenarioRunner(uri=GMT_ROOT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/metric_providers_data.yml', skip_system_checks=True, dev_no_metrics=False, dev_no_sleeps=True, dev_cache_build=True)

    subprocess.run('sync', check=True) # we sync here so that we can later more granular check for written file size

    run_id = runner.run()

def get_disk_usage(path="/"):
    usage = psutil.disk_usage(path)
    total = usage.total
    used = usage.used
    free = usage.free
    return {'total': total, 'used': used, 'free': free}

# Is used when the file needs to be modified
def mock_temporary_file(file_path, temp_file):
    with open(file_path, 'r', encoding='utf-8') as file:
        file_contents = file.read()

    # Write the modified contents back to the file
    with open(temp_file, 'w', encoding='utf-8') as file:
        file.write(file_contents)

def mock_temporary_network_file(file_path, temp_file, actual_network_interface):
    with open(file_path, 'r', encoding='utf-8') as file:
        file_contents = file.read()

    # Replace every occurrence of the old string with the new string
    modified_contents = file_contents.replace('CURRENT_ACTUAL_NETWORK_INTERFACE', actual_network_interface)

    # Write the modified contents back to the file
    with open(temp_file, 'w', encoding='utf-8') as file:
        file.write(modified_contents)

@pytest.mark.skipif(utils.get_architecture() == 'macos', reason="macOS does not support networkIO capturing on adapter level atm")
def test_splitting_by_group():
    obj = NetworkIoProcfsSystemProvider(99, remove_virtual_interfaces=False)

    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        mock_temporary_network_file('./data/metrics/network_io_procfs_system_two_measurements_at_phase_border_out.log', temp_file.name, 'MY_FAKE_INTERFACE')

        obj._filename = temp_file.name
        df = obj.read_metrics()

    assert df[df['detail_name'] == 'lo']['value'].sum() == 0
    assert df[df['detail_name'] == 'lo']['value'].count() != 0, 'Grouping and filtering resulted in zero result lines for network_io'

@pytest.mark.skipif(utils.get_architecture() == 'macos', reason="macOS does not support disk used capturing atm")
def test_disk_providers():

    assert(run_id is not None and run_id != '')

    query = """
            SELECT metric, detail_name, value, unit, max_value
            FROM phase_stats
            WHERE run_id = %s and phase = '005_Download'
            """
    data = DB().fetch_all(query, (run_id,), fetch_mode='dict')
    assert(data is not None and data != [])

    ## get the current used disj
#    seen_disk_total_procfs_system = False
    seen_disk_used_statvfs_system = False

    for metric_provider in data:
        metric = metric_provider['metric']
        val = metric_provider['value'] #pylint: disable=unused-variable
        max_value = metric_provider['max_value']

        if metric == 'disk_used_statvfs_system':
            disk_usage = get_disk_usage()
            # since some small write might have occured we allow a margin of 10 MB which seems reasonable for waiting flushes
            assert (max_value - disk_usage['used']) < 10*MB, f"disk_used_statvfs_system is not close (10 MB) to {disk_usage['used']} but {max_value} {metric_provider['unit']}"
            seen_disk_used_statvfs_system = True
# This one is disabled for now as we are seeing strange issues in Github VMs seeing an additional physical block device (sda16)
#        elif metric == 'disk_total_procfs_system':
#            # Since some other sectors are flushed we need to account for a margin
#            assert 5*MB <= val <= 7*MB , f"disk_total_procfs_system is not between 5 and 7 MB but {metric_provider['value']} {metric_provider['unit']}"
#            seen_disk_total_procfs_system = True

 #   assert seen_disk_total_procfs_system is True
    assert seen_disk_used_statvfs_system is True

@pytest.mark.skipif(utils.get_architecture() == 'macos', reason="Network Cgroup tests are not possible under macOS due to missing cgroup functionality")
def test_network_providers():
    assert(run_id is not None and run_id != '')

    # Different to the other tests here we need to aggregate over all network interfaces
    query = """
            SELECT metric, SUM(value) as value, unit
            FROM phase_stats
            WHERE run_id = %s and phase = '005_Download' AND metric = 'network_total_procfs_system'
            GROUP BY metric, unit
    """

    data = DB().fetch_all(query, (run_id,), fetch_mode='dict')
    assert(data is not None and data != [])

    for metric_provider in data:
        val = metric_provider['value']

        # Some small network overhead to a 5 MB file always occurs
        # See discussion for details on how much believe is acceaptable and for which reasons here: https://github.com/green-coding-solutions/green-metrics-tool/issues/1322
        assert 5*MB <= val < 6*MB , f"network_total_procfs_system is not between 5 and 6 MB but {val} {metric_provider['unit']}"

@pytest.mark.skipif(os.getenv("GITHUB_ACTIONS") == "true" or utils.get_architecture() == 'macos', reason='Skip test for GitHub Actions VM as memory seems weirdly assigned here. Also skip macos as memory assignment is virtualized in VM')
def test_memory_providers():

    assert(run_id is not None and run_id != '')

    query = """
            SELECT metric, detail_name, value, unit, max_value
            FROM phase_stats
            WHERE
                run_id = %s and phase = '006_VM Stress' AND metric = 'memory_used_procfs_system'
            ORDER BY metric DESC -- this will assure that the phase_time metric will come first and can be saved
            """

    data = DB().fetch_all(query, (run_id,), fetch_mode='dict')
    assert(data is not None and data != [])

    for metric_provider in data:
        val = metric_provider['value']

        assert psutil.virtual_memory().total*0.55 <= val <= psutil.virtual_memory().total * 0.65 , f"memory_used_procfs_system avg is not between 55% and 65% of total memory but {val} {metric_provider['unit']}"

def test_cpu_time_carbon_providers():

    assert(run_id is not None and run_id != '')

    query = """
            SELECT metric, detail_name, value, unit, max_value
            FROM phase_stats
            WHERE
                run_id = %s and phase = '007_CPU Stress'
            ORDER BY metric DESC -- this will assure that the phase_time metric will come first and can be saved
            """

    data = DB().fetch_all(query, (run_id,), fetch_mode='dict')
    assert(data is not None and data != [])

    seen_phase_time_syscall_system = False
    seen_cpu_utilization_system = False
    seen_cpu_utilization_cgroup_container = False
    seen_embodied_carbon_share_machine = False
    phase_time = None

    # will result in value <= 1 and thus pro-rate the targeted 90+ utilization of the whole system
    max_utilization_factor = resource_limits.get_assignable_cpus() / os.cpu_count()

    for metric_provider in data:
        metric = metric_provider['metric']
        val = metric_provider['value']
        max_value = metric_provider['max_value']


        if metric == 'cpu_utilization_cgroup_container':
            assert 9000 < val <= 10000, f"cpu_utilization_cgroup_container is not between 90_00 and 100_00 but {val} {metric_provider['unit']}"
            assert 9500 < max_value <= 10500, f"cpu_utilization_cgroup_container max is not between 95_00 and 105_00 but {max_value} {metric_provider['unit']}"

            seen_cpu_utilization_cgroup_container = True

        elif metric == 'cpu_utilization_procfs_system':
            assert 9000 * max_utilization_factor < val <= 10000 * max_utilization_factor , f"{metric} is not between {9000 * max_utilization_factor} and {10000 * max_utilization_factor} but {val} {metric_provider['unit']}"
            assert 9500 * max_utilization_factor < max_value <= 10500 * max_utilization_factor , f"{metric} max is not between {9500 * max_utilization_factor} and {10500 * max_utilization_factor} but {max_value} {metric_provider['unit']}"

            seen_cpu_utilization_system = True

        elif metric == 'cpu_utilization_mach_system':
            # Since macOS is such a noisy system it is hard to find a "range" where the numbers shall be. The only thing we really know is that it must be higher than what is happening in the VM. but it can be actually up to a 100% (plus a bit calculatory overhead ... so we do 105%)
            assert 100_00 * max_utilization_factor < val <= 105_00, f"{metric} is not greater than {100_00 * max_utilization_factor} but {val} {metric_provider['unit']}"
            seen_cpu_utilization_system = True

        elif metric == 'phase_time_syscall_system':
            seen_phase_time_syscall_system = True
            phase_time = val

            assert 5*MICROSECONDS < val < 6*MICROSECONDS , f"phase_time_syscall_system is not between 5 and 6 s but {val} {metric_provider['unit']}"

        elif metric == 'embodied_carbon_share_machine':
            # we have the phase time value as we sort by metric DESC
            phase_time_in_years = phase_time / (MICROSECONDS * 60 * 60 * 24 * 365)
            sci = {"EL": 4, "TE": 181000, "RS": 1}
            embodied_carbon_expected = int((phase_time_in_years / sci['EL']) * sci['TE'] * sci['RS'] * 1_000_000)
            # Make a range because of rounding errors
            assert embodied_carbon_expected*0.99 < val < embodied_carbon_expected*1.01  , f"embodied_carbon_share_machine is not {embodied_carbon_expected} but {val} {metric_provider['unit']}\n. This might be also because the values in the test are hardcoded. Check reporter but also if test-config.yml configuration is still accurate"
            seen_embodied_carbon_share_machine = True

    assert seen_phase_time_syscall_system is True, "Did not see phase_time_syscall_system metric"
    assert seen_cpu_utilization_system is True, "Did not see scpu_utilization_[procfs|mach]_system metric"
    assert seen_embodied_carbon_share_machine is True, "Did not see seen_embodied_carbon_share_machine metric"

    assert seen_cpu_utilization_cgroup_container is True or utils.get_architecture() == 'macos', "Did not see cpu_utilization_cgroup_container metric"
