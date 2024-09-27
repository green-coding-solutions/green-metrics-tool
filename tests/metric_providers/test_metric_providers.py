import os
import tempfile
import psutil
import subprocess

GMT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))+'/../../'

from lib.db import DB
from lib import utils
from lib.global_config import GlobalConfig
from runner import Runner
from metric_providers.network.io.procfs.system.provider import NetworkIoProcfsSystemProvider
from tools.phase_stats import build_and_store_phase_stats


GlobalConfig().override_config(config_name='test-config.yml')
config = GlobalConfig().config

def get_disk_usage(path="/"):
    usage = psutil.disk_usage(path)
    total = usage.total
    used = usage.used
    free = usage.free
    return {'total': total, 'used': used, 'free': free}

def mock_temporary_network_file(file_path, temp_file, actual_network_interface):
    with open(file_path, 'r', encoding='utf-8') as file:
        file_contents = file.read()

    # Replace every occurrence of the old string with the new string
    modified_contents = file_contents.replace('CURRENT_ACTUAL_NETWORK_INTERFACE', actual_network_interface)

    # Write the modified contents back to the file
    with open(temp_file, 'w', encoding='utf-8') as file:
        file.write(modified_contents)

def test_splitting_by_group():

    obj = NetworkIoProcfsSystemProvider(100, remove_virtual_interfaces=False)

    actual_network_interface = utils.get_network_interfaces(mode='physical')[0]
    with tempfile.NamedTemporaryFile(delete=True) as temp_file:
        mock_temporary_network_file('./data/metrics/network_io_procfs_system.log', temp_file.name, actual_network_interface)

        obj._filename = temp_file.name
        df = obj.read_metrics('RUN_ID')

    assert df[df['detail_name'] == 'lo']['value'].sum() == 0
    assert df[df['detail_name'] == 'lo']['value'].count() != 0, 'Grouping and filtering resulted in zero result lines for network_io'

def test_io_providers():
    if utils.get_architecture() == 'macos':
        return

    runner = Runner(uri=GMT_ROOT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/data_download_5MB.yml', skip_system_checks=True, dev_no_metrics=False, dev_no_sleeps=True, dev_no_build=True)

    subprocess.run('sync', check=True) # we sync here so that we can later more granular check for written file size

    run_id = runner.run()

    assert(run_id is not None and run_id != '')

    build_and_store_phase_stats(runner._run_id, runner._sci)

    query = """
            SELECT metric, detail_name, phase, value, unit, max_value
            FROM phase_stats
            WHERE run_id = %s and phase = '004_[RUNTIME]'
            """
    data = DB().fetch_all(query, (run_id,), fetch_mode='dict')
    assert(data is not None and data != [])

    ## get the current used disj
    seen_disk_total_procfs_system = False
    seen_network_total_procfs_system = False
    seen_disk_used_statvfs_system = False
    MB = 1024*1024
    for metric_provider in data:
        metric = metric_provider['metric']
        val = metric_provider['value']
        max_value = metric_provider['max_value']

        if metric == 'disk_total_procfs_system':
            # Since some other sectors are flushed we need to account for a margin
            assert 5*MB <= val <= 6*MB , f"disk_total_procfs_system is not between 5 and 6 MB but {metric_provider['value']} {metric_provider['unit']}"
            seen_disk_total_procfs_system = True
        elif metric == 'network_total_procfs_system':
            # Some small network overhead to a 5 MB file always occurs
            assert 5*MB <= val < 5.5*MB , f"network_total_procfs_system is not between 5 and 5.5 MB but {metric_provider['value']} {metric_provider['unit']}"
            seen_network_total_procfs_system = True
        elif metric == 'disk_used_statvfs_system':
            disk_usage = get_disk_usage()
            # since some small write might have occured we allow a margin of 10 MB which seems reasonable for waiting flushes
            assert (max_value - disk_usage['used']) < 10*MB, f"disk_used_statvfs_system is not close (10 MB) to {disk_usage['used']} but {max_value} {metric_provider['unit']}"
            seen_disk_used_statvfs_system = True

    assert seen_disk_total_procfs_system is True
    assert seen_network_total_procfs_system is True
    assert seen_disk_used_statvfs_system is True

def test_cpu_memory_providers():
    if utils.get_architecture() == 'macos':
        return

    runner = Runner(uri=GMT_ROOT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/memory_stress.yml', skip_system_checks=True, dev_no_metrics=False, dev_no_sleeps=True, dev_no_build=True)
    run_id = runner.run()

    assert(run_id is not None and run_id != '')

    build_and_store_phase_stats(runner._run_id, runner._sci)

    query = """
            SELECT metric, detail_name, phase, value, unit, max_value
            FROM phase_stats
            WHERE run_id = %s and phase = '004_[RUNTIME]'
            """

    data = DB().fetch_all(query, (run_id,), fetch_mode='dict')
    assert(data is not None and data != [])

    ## get the current used disj
 #   seen_phase_time_syscall_system = False
    seen_cpu_utilization_procfs_system = False
    seen_memory_used_procfs_system = False

    for metric_provider in data:
        metric = metric_provider['metric']
        val = metric_provider['value']
        max_value = metric_provider['max_value']

        if metric == 'cpu_utilization_procfs_system':
            assert 9000 < val <= 10000 , f"cpu_utilization_procfs_system is not between 90_00 and 100_00 MB but {metric_provider['value']} {metric_provider['unit']}"
            assert 9500 < max_value <= 10000 , f"cpu_utilization_procfs_system max is not between 95_00 and 100_00 MB but {metric_provider['value']} {metric_provider['unit']}"

            seen_cpu_utilization_procfs_system = True
        elif metric == 'memory_used_procfs_system':
            assert val > psutil.virtual_memory().total * 0.5 , f"memory_used_procfs_system avg is not > 50% of total memory. This is too low ... but {metric_provider['value']} {metric_provider['unit']}"
            assert max_value > psutil.virtual_memory().total * 0.8 , f"memory_used_procfs_system max is not > 80% of total memory. This is too low ... but {metric_provider['max_value']} {metric_provider['unit']}"

            seen_memory_used_procfs_system = True
        # check for phase_time proved tricky. The stress --vm blocks the system so hard that the 5 second timeout cannot be guaranteed
#        elif metric == 'phase_time_syscall_system':
#            assert val > 5 and val < 5.1 , f"phase_time_syscall_system is not between 5 and 5.1 s but {metric_provider['value']} {metric_provider['unit']}"
#            seen_phase_time_syscall_system = True

#    assert seen_phase_time_syscall_system == True
    assert seen_cpu_utilization_procfs_system is True
    assert seen_memory_used_procfs_system is True
