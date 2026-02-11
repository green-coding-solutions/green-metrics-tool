import os
import math
import pytest
import shutil

from pathlib import Path

GMT_ROOT_DIR = Path(__file__).parent.parent.parent.as_posix()

from tests import test_functions as Tests

from metric_providers.network.io.procfs.system.provider import NetworkIoProcfsSystemProvider
from metric_providers.cpu.energy.rapl.msr.component.provider import CpuEnergyRaplMsrComponentProvider
from metric_providers.network.connections.tcpdump.system.provider import NetworkConnectionsTcpdumpSystemProvider, generate_stats_string
from metric_providers.powermetrics.provider import PowermetricsProvider
from metric_providers.psu.energy.ac.xgboost.machine.provider import PsuEnergyAcXgboostMachineProvider
from metric_providers.cpu.utilization.cgroup.system.provider import CpuUtilizationCgroupSystemProvider
from metric_providers.cpu.utilization.cgroup.container.provider import CpuUtilizationCgroupContainerProvider

from unittest.mock import patch

GMT_METRICS_DIR = Path('/tmp/green-metrics-tool/metrics')

## Create a tmp folder only for this run
@pytest.fixture(autouse=True, scope='module')
def setup_test_metrics_tmp_folder():
    GMT_METRICS_DIR.mkdir(parents=True, exist_ok=True) # might be deleted depending on which tests run before
    yield
    shutil.rmtree(GMT_METRICS_DIR)

def test_check_unique_time_values():
    obj = CpuUtilizationCgroupContainerProvider(100, folder=GMT_METRICS_DIR, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/cpu_utilization_cgroup_container_non_unique.log')
    with pytest.raises(ValueError) as e:
        obj.read_metrics()
    assert str(e.value) == 'Metric provider cpu_utilization_cgroup_container did contain non unique timestamps for measurement values. This is not allowed and indicates an error with the clock.'



def test_time_monotonic():
    obj = NetworkIoProcfsSystemProvider(100, remove_virtual_interfaces=False, folder=GMT_METRICS_DIR, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/network_io_procfs_system.log')
    obj.read_metrics()


def test_time_non_monotonic():
    obj = NetworkIoProcfsSystemProvider(1000, remove_virtual_interfaces=False, folder=GMT_METRICS_DIR, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/network_io_procfs_system_non_monotonic.log')
    with pytest.raises(ValueError) as e:
        obj.read_metrics()

    assert str(e.value) == 'Time from metric provider network_io_procfs_system is not monotonic increasing'

def test_value_resolution_ok():
    obj = CpuEnergyRaplMsrComponentProvider(100, folder=GMT_METRICS_DIR, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/cpu_energy_rapl_msr_component.log')
    obj.read_metrics()

def test_value_resolution_underflow():
    obj = CpuEnergyRaplMsrComponentProvider(1000, folder=GMT_METRICS_DIR, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/cpu_energy_rapl_msr_component_underflow.log')

    with pytest.raises(ValueError) as e:
        obj.read_metrics()
    assert str(e.value) == 'Data from metric provider cpu_energy_rapl_msr_component is running into a resolution underflow. Values are <= 1 uJ'

def test_tcpdump_linux():
    obj = NetworkConnectionsTcpdumpSystemProvider(folder=GMT_METRICS_DIR, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/network_connections_tcpdump_system_linux.log')

    data = obj.read_metrics()


    stats = generate_stats_string(data)

    # ipv6 match
    assert '''IP: 2003:fb:7f37:2900:25cf:2275:1b6a:5818 (as sender or receiver. aggregated)
  Total transmitted data: 1107261 bytes
  Ports:
    49871/TCP: 1 packets, 20 bytes
    49872/TCP: 225 packets, 1107241 bytes''' in stats

    # ipv4 match
    assert '''IP: 5.75.242.14 (as sender or receiver. aggregated)
  Total transmitted data: 2552885 bytes
  Ports:
    22/TCP: 784 packets, 355463 bytes
    0/ICMP: 1 packets, 80 bytes
    9573/ICMP: 1 packets, 80 bytes
    8568/TCP: 2 packets, 80 bytes
    5855/TCP: 2 packets, 84 bytes
    46899/UDP: 2 packets, 164 bytes
    9573/TCP: 1476 packets, 2196934 bytes''' in stats

    # many packet correct aggregation
    assert '59979/TCP: 556 packets, 326552 bytes' in stats

    # LLDP match
    assert '''IP: - (as sender or receiver. aggregated)
  Total transmitted data: 2640 bytes
  Ports:
    -/LLDP: 20 packets, 2640 bytes''' in stats

    # etherframe match
    assert '''IP: Unknown Port (as sender or receiver. aggregated)
  Total transmitted data: 51120 bytes
  Ports:
    Unknown Port/Unknown Etherframe: 852 packets, 51120 bytes''' in stats

    # ICMPv6 match
    assert '''IP: fe80::921b:eff:feff:55b4 (as sender or receiver. aggregated)
  Total transmitted data: 336 bytes
  Ports:
    0/ICMPv6: 12 packets, 336 bytes''' in stats

    # options match
    assert '''IP: fe80::921b:eff:fed8:2619 (as sender or receiver. aggregated)
  Total transmitted data: 72 bytes
  Ports:
    0/Options: 2 packets, 72 bytes''' in stats

    # IGMP match
    assert '''IP: 192.168.178.1 (as sender or receiver. aggregated)
  Total transmitted data: 260 bytes
  Ports:
    0/IGMP: 4 packets, 216 bytes
    53805/UDP: 1 packets, 44 bytes''' in stats

    # UDP broadcast match
    assert '''IP: ff0e::c (as sender or receiver. aggregated)
  Total transmitted data: 2759 bytes
  Ports:
    1900/UDP: 8 packets, 2759 bytes''' in stats


def test_tcpdump_macos():
    obj = NetworkConnectionsTcpdumpSystemProvider(folder=GMT_METRICS_DIR, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/network_connections_tcpdump_system_macos.log')

    data = obj.read_metrics()

    stats = generate_stats_string(data)

    # IP match
    assert '''IP: 192.168.178.40 (as sender or receiver. aggregated)
  Total transmitted data: 336382 bytes
  Ports:
    50417/TCP: 16 packets, 3318 bytes
    50352/TCP: 6 packets, 356 bytes
    50421/TCP: 9 packets, 492 bytes
    50080/TCP: 5 packets, 2428 bytes
    50422/TCP: 25 packets, 7309 bytes
    50423/TCP: 25 packets, 6982 bytes
    50124/TCP: 2 packets, 191 bytes
    60933/UDP: 2 packets, 130 bytes
    54453/UDP: 2 packets, 120 bytes
    62504/UDP: 2 packets, 229 bytes
    60482/UDP: 2 packets, 249 bytes
    50416/TCP: 282 packets, 314258 bytes
    59713/UDP: 4 packets, 320 bytes''' in stats

    # Etherframe match
    assert '''IP: Unknown Port (as sender or receiver. aggregated)
  Total transmitted data: 2400 bytes
  Ports:
    Unknown Port/Unknown Etherframe: 40 packets, 2400 bytes''' in stats

    # ICMPv6 match
    assert '''IP: fe80::b0de:28ff:fe27:c164 (as sender or receiver. aggregated)
  Total transmitted data: 88 bytes
  Ports:
    0/ICMPv6: 1 packets, 88 bytes''' in stats

    # UDP only match (QUIC)
    assert '''IP: 172.217.19.74 (as sender or receiver. aggregated)
  Total transmitted data: 320 bytes
  Ports:
    443/UDP: 4 packets, 320 bytes''' in stats

def test_powermetrics():
    obj = PowermetricsProvider(499, folder=GMT_METRICS_DIR, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/powermetrics.log')

    df = obj.read_metrics()

    assert list(df.metric.unique()) == ['cpu_time_powermetrics_vm', 'disk_io_bytesread_powermetrics_vm', 'disk_io_byteswritten_powermetrics_vm', 'energy_impact_powermetrics_vm', 'cores_energy_powermetrics_component', 'gpu_energy_powermetrics_component', 'ane_energy_powermetrics_component']

    assert math.isclose(df[df.metric == 'energy_impact_powermetrics_vm'].value.mean(), 430.823529, rel_tol=1e-5)

def test_cloud_energy():
    filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/cpu_utilization_mach_system.log')
    obj = PsuEnergyAcXgboostMachineProvider(HW_CPUFreq=4000, CPUChips=1, CPUThreads=1, TDP=160,
                 HW_MemAmountGB=4, folder=GMT_METRICS_DIR, skip_check=True, filename=filename)

    df = obj.read_metrics()

    assert df.metric.unique() == ['psu_energy_ac_xgboost_machine']

    assert math.isclose(df[df.metric == 'psu_energy_ac_xgboost_machine'].value.mean(), 7076857.12, rel_tol=1e-5)

def test_cgroup_system():
    with patch('lib.utils.find_own_cgroup_name') as find_own_cgroup_name:
        find_own_cgroup_name.return_value = 'session-2.scope'
        obj = CpuUtilizationCgroupSystemProvider(100, folder=GMT_METRICS_DIR, skip_check=True)

    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/cpu_utilization_cgroup_system.log')

    df = obj.read_metrics()

    assert df.metric.unique() == ['cpu_utilization_cgroup_system']
    assert df.detail_name.unique() == 'GMT Overhead'
    assert math.isclose(df.value.mean(), 539.3809, rel_tol=1e-5)

def test_cgroup_container():
    obj = CpuUtilizationCgroupContainerProvider(100, folder=GMT_METRICS_DIR, skip_check=True)

    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/cpu_utilization_cgroup_container.log')

    obj.add_containers(Tests.TEST_MEASUREMENT_CONTAINERS)
    df = obj.read_metrics()

    assert df.metric.unique() == ['cpu_utilization_cgroup_container']
    assert list(df.detail_name.unique()) == ['38d1e484f336c40a6e60e4518915a4e385f62fdddd47994d6adcb4fb294b2ec8', '939f410a21730a2275e91b8a949884f7f426b89e50e8b2ffceca271b6a4573b6']

    assert math.isclose(df.value.mean(), 289.595, rel_tol=1e-5)
