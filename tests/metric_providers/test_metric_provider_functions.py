import os
import math
import pytest

GMT_ROOT_DIR = os.path.dirname(os.path.abspath(__file__))+'/../../'

from metric_providers.network.io.procfs.system.provider import NetworkIoProcfsSystemProvider
from metric_providers.cpu.energy.rapl.msr.component.provider import CpuEnergyRaplMsrComponentProvider
from metric_providers.network.connections.tcpdump.system.provider import NetworkConnectionsTcpdumpSystemProvider, generate_stats_string
from metric_providers.powermetrics.provider import PowermetricsProvider
from metric_providers.psu.energy.ac.xgboost.machine.provider import PsuEnergyAcXgboostMachineProvider

def test_time_monotonic():
    obj = NetworkIoProcfsSystemProvider(1000, remove_virtual_interfaces=False, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/network_io_procfs_system_short.log')
    obj.read_metrics()


def test_time_non_monotonic():
    obj = NetworkIoProcfsSystemProvider(1000, remove_virtual_interfaces=False, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/network_io_procfs_system_non_monotonic.log')
    with pytest.raises(ValueError) as e:
        obj.read_metrics()

    assert str(e.value) == "Time from metric provider network_io_procfs_system is not monotonic increasing"

def test_value_resolution_ok():
    obj = CpuEnergyRaplMsrComponentProvider(1000, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/cpu_energy_rapl_msr_component_short.log')
    obj.read_metrics()

def test_value_resolution_underflow():
    obj = CpuEnergyRaplMsrComponentProvider(1000, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/cpu_energy_rapl_msr_component_underflow.log')

    with pytest.raises(ValueError) as e:
        obj.read_metrics()
    assert str(e.value) == "Data from metric provider cpu_energy_rapl_msr_component is running into a resolution underflow. Values are <= 1 mJ"

def test_tcpdump_linux():
    obj = NetworkConnectionsTcpdumpSystemProvider(1000, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/network_connections_tcpdump_system_linux.log')

    data = obj.read_metrics()


    stats = generate_stats_string(data)

    assert '59979/TCP: 556 packets, 326552 bytes' in stats
    assert 'None/ICMP: 2 packets, 160 bytes' in stats # Note: ICMP can have NONE as src/dst port as it sends discovery packets that might not be routable
    assert 'IP: 2003:fb:7f37:2900:25cf:2275:1b6a:5818 (as sender or receiver. aggregated)' in stats

def test_tcpdump_macos():
    obj = NetworkConnectionsTcpdumpSystemProvider(1000, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/network_connections_tcpdump_system_macos.log')

    data = obj.read_metrics()

    stats = generate_stats_string(data)

    assert 'IP: 172.217.19.74 (as sender or receiver. aggregated)' in stats
    assert 'Unknown Port/Unknown Etherframe: 40 packets, 2400 bytes' in stats
    assert '50417/TCP: 16 packets, 3318 bytes' in stats

def test_powermetrics():
    obj = PowermetricsProvider(499, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/powermetrics.log')

    df = obj.read_metrics()

    assert list(df.metric.unique()) == ['cpu_time_powermetrics_vm', 'disk_io_bytesread_powermetrics_vm', 'disk_io_byteswritten_powermetrics_vm', 'energy_impact_powermetrics_vm', 'cores_energy_powermetrics_component', 'gpu_energy_powermetrics_component', 'ane_energy_powermetrics_component']

    assert math.isclose(df[df.metric == 'energy_impact_powermetrics_vm'].value.mean(), 430.823529, rel_tol=1e-5)

def test_cloud_energy():
    filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/cpu_utilization_mach_system.log')
    obj = PsuEnergyAcXgboostMachineProvider(100, HW_CPUFreq=4000, CPUChips=1, CPUThreads=1, TDP=160,
                 HW_MemAmountGB=4, skip_check=True, filename=filename)

    df = obj.read_metrics()

    assert df.metric.unique() == ['psu_energy_ac_xgboost_machine']

    assert math.isclose(df[df.metric == 'psu_energy_ac_xgboost_machine'].value.mean(), 10055.48076, rel_tol=1e-5)
