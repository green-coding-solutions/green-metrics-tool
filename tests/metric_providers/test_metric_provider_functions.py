import os
import math
import pytest
import shutil
import tempfile

from io import StringIO
from pathlib import Path

GMT_ROOT_DIR = Path(__file__).parent.parent.parent.as_posix()

from tests import test_functions as Tests

from metric_providers.network.io.procfs.system.provider import NetworkIoProcfsSystemProvider
from metric_providers.cpu.energy.rapl.msr.component.provider import CpuEnergyRaplMsrComponentProvider
from metric_providers.network.connections.tcpdump.system.provider import NetworkConnectionsTcpdumpSystemProvider, generate_stats_string
from metric_providers.network.connections.tcpdump.container.provider import NetworkConnectionsTcpdumpContainerProvider, _resolve_veths
from metric_providers.base import MetricProviderConfigurationError
from metric_providers.powermetrics.provider import PowermetricsProvider
from metric_providers.psu.energy.ac.xgboost.machine.provider import PsuEnergyAcXgboostMachineProvider
from metric_providers.cpu.utilization.cgroup.system.provider import CpuUtilizationCgroupSystemProvider
from metric_providers.cpu.utilization.cgroup.container.provider import CpuUtilizationCgroupContainerProvider

from unittest.mock import patch

from lib.db import DB

GMT_METRICS_DIR = Path(tempfile.mkdtemp(prefix='green-metrics-tool-metrics-'))

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

    assert DB().fetch_one('SELECT COUNT(*) FROM system_logs')[0] == 0, 'system_logs must be empty - tcpdump parser emitted unexpected errors'


def test_tcpdump_linux_vlan():
    obj = NetworkConnectionsTcpdumpSystemProvider(folder=GMT_METRICS_DIR, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/network_connections_tcpdump_system_linux_vlan.log')

    data = obj.read_metrics()

    stats = generate_stats_string(data)

    assert DB().fetch_one('SELECT COUNT(*) FROM system_logs')[0] == 0, 'system_logs must be empty - tcpdump parser emitted unexpected errors'


    # IPv4 match
    assert '''IP: 192.168.30.17 (as sender or receiver. aggregated)
  Total transmitted data: 3005 bytes
  Ports:
    56722/TCP: 9 packets, 2585 bytes
    43387/UDP: 2 packets, 144 bytes
    40932/UDP: 2 packets, 138 bytes
    49483/UDP: 2 packets, 138 bytes''' in stats


    # IPv6 match
    assert '''IP: fe80::d2ea:11ff:fe0d:f2ae (as sender or receiver. aggregated)
  Total transmitted data: 181 bytes
  Ports:
    5678/UDP: 1 packets, 181 bytes''' in stats

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

    assert DB().fetch_one('SELECT COUNT(*) FROM system_logs')[0] == 0, 'system_logs must be empty - tcpdump parser emitted unexpected errors'


def test_tcpdump_container_parse_metrics_groups_by_interface():
    obj = NetworkConnectionsTcpdumpContainerProvider(folder=GMT_METRICS_DIR, skip_check=True)
    obj._interface_to_detail_name = {
        'veth1111aaaa': 'container-a',
        'veth2222bbbb': 'container-b',
    }

    lines = [
        # container-a: single-line-header + indented continuation (2 packets, same TCP flow)
        '1735295414.719551 veth1111aaaa In  IP (tos 0x10, ttl 64, id 12590, offset 0, flags [DF], proto TCP (6), length 176)\n',
        '    5.75.242.14.22 > 79.224.127.251.59979: Flags [P.], cksum 0xc7d7 (incorrect -> 0xa394), seq 458946148:458946272, ack 3869229696, win 501, options [nop,nop,TS val 4068070828 ecr 4289544055], length 124\n',
        '1735295414.740639 veth1111aaaa Out IP (tos 0x0, ttl 55, id 0, offset 0, flags [none], proto TCP (6), length 52)\n',
        '    79.224.127.251.59979 > 5.75.242.14.22: Flags [.], cksum 0xfa28 (correct), ack 124, win 2046, options [nop,nop,TS val 4289544143 ecr 4068070828], length 0\n',
        # container-b: different flow entirely
        '1735295414.806828 veth2222bbbb In  IP (tos 0x10, ttl 64, id 12591, offset 0, flags [DF], proto TCP (6), length 192)\n',
        '    10.0.0.5.443 > 10.0.0.6.51000: Flags [P.], cksum 0xc7e7 (incorrect -> 0x45be), seq 124:264, ack 1, win 501, options [nop,nop,TS val 4068070915 ecr 4289544143], length 140\n',
        # traffic on an interface we did not ask to monitor - must be dropped entirely, including its continuation line
        '1735295414.900000 vethUNMONITORED In  IP (tos 0x10, ttl 64, id 1, offset 0, flags [DF], proto TCP (6), length 100)\n',
        '    1.2.3.4.1 > 1.2.3.5.2: Flags [P.], cksum 0x0000 (correct), seq 1:2, ack 1, win 1, options [nop], length 1\n',
    ]

    result = obj._parse_metrics(lines)

    assert set(result.keys()) == {'container-a', 'container-b'}

    stats_a = generate_stats_string(result['container-a'])
    # both packets involve port 22/TCP on 5.75.242.14 (once as sender, once as receiver),
    # so packets/bytes accumulate across both of them: 176 + 52 = 228
    assert '''IP: 5.75.242.14 (as sender or receiver. aggregated)
  Total transmitted data: 228 bytes
  Ports:
    22/TCP: 2 packets, 228 bytes''' in stats_a
    assert '79.224.127.251' in stats_a

    stats_b = generate_stats_string(result['container-b'])
    assert 'IP: 10.0.0.5 (as sender or receiver. aggregated)' in stats_b
    assert '10.0.0.6' in stats_b

    # traffic from the unmonitored interface must not leak into either container
    assert '1.2.3.4' not in stats_a and '1.2.3.4' not in stats_b
    assert '1.2.3.5' not in stats_a and '1.2.3.5' not in stats_b


def test_tcpdump_container_add_extra_switches_requires_containers():
    obj = NetworkConnectionsTcpdumpContainerProvider(folder=GMT_METRICS_DIR, skip_check=True)
    with pytest.raises(MetricProviderConfigurationError):
        obj._add_extra_switches('tcpdump.sh')


def test_tcpdump_container_add_extra_switches_builds_ifname_filter():
    obj = NetworkConnectionsTcpdumpContainerProvider(folder=GMT_METRICS_DIR, skip_check=True)
    obj._interface_to_detail_name = {'veth1111aaaa': 'container-a', 'veth2222bbbb': 'container-b'}

    call_string = obj._add_extra_switches('tcpdump.sh')

    assert call_string == "tcpdump.sh -f 'ifname veth1111aaaa or ifname veth2222bbbb'"


def test_tcpdump_container_resolve_veths_multi_interface():
    with patch('subprocess.check_output') as mock_check_output, \
         patch('os.listdir') as mock_listdir, \
         patch('builtins.open') as mock_open:

        def check_output_side_effect(cmd, **_kwargs):
            if cmd[:2] == ['docker', 'inspect']:
                return '4242'
            if cmd[-1] == '/sys/class/net' or cmd[-2:] == ['ls', '/sys/class/net']:
                return 'lo eth0 eth1'
            if cmd[-1].endswith('/eth0/iflink'):
                return '101'
            if cmd[-1].endswith('/eth1/iflink'):
                return '102'
            raise AssertionError(f'unexpected command: {cmd}')

        mock_check_output.side_effect = check_output_side_effect
        mock_listdir.return_value = ['lo', 'veth1111aaaa', 'veth2222bbbb', 'eth0']

        def open_side_effect(path, *_args, **_kwargs):
            if path == '/sys/class/net/veth1111aaaa/ifindex':
                return StringIO('101\n')
            if path == '/sys/class/net/veth2222bbbb/ifindex':
                return StringIO('102\n')
            raise AssertionError(f'unexpected open: {path}')

        mock_open.side_effect = open_side_effect

        veths = _resolve_veths('deadbeef1234')

        assert sorted(veths) == ['veth1111aaaa', 'veth2222bbbb']


def test_tcpdump_container_resolve_veths_not_found_raises():
    with patch('subprocess.check_output') as mock_check_output, \
         patch('os.listdir', return_value=['lo']):

        def check_output_side_effect(cmd, **_kwargs):
            if cmd[:2] == ['docker', 'inspect']:
                return '4242'
            if cmd[-2:] == ['ls', '/sys/class/net']:
                return 'lo eth0'
            if cmd[-1].endswith('/eth0/iflink'):
                return '999'
            raise AssertionError(f'unexpected command: {cmd}')

        mock_check_output.side_effect = check_output_side_effect

        with pytest.raises(MetricProviderConfigurationError):
            _resolve_veths('deadbeef1234')

def test_powermetrics():
    obj = PowermetricsProvider(499, folder=GMT_METRICS_DIR, skip_check=True)
    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/powermetrics.log')

    df = obj.read_metrics()

    assert list(df.metric.unique()) == ['cpu_time_powermetrics_vm', 'disk_io_bytesread_powermetrics_vm', 'disk_io_byteswritten_powermetrics_vm', 'energy_impact_powermetrics_vm', 'cores_energy_powermetrics_component', 'gpu_energy_powermetrics_component', 'ane_energy_powermetrics_component']

    assert math.isclose(df[df.metric == 'energy_impact_powermetrics_vm'].value.mean(), 430.823529, abs_tol=1e-3)

def test_cloud_energy():
    filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/cpu_utilization_mach_system.log')
    obj = PsuEnergyAcXgboostMachineProvider(HW_CPUFreq=4000, CPUChips=1, CPUThreads=1, TDP=160,
                 HW_MemAmountGB=4, folder=GMT_METRICS_DIR, skip_check=True, filename=filename)

    df = obj.read_metrics()

    assert df.metric.unique() == ['psu_energy_ac_xgboost_machine']

    assert math.isclose(df[df.metric == 'psu_energy_ac_xgboost_machine'].value.mean(), 7076857.12, abs_tol=1e-3)

def test_cgroup_system():
    with patch('lib.utils.find_own_cgroup_name') as find_own_cgroup_name:
        find_own_cgroup_name.return_value = 'session-2.scope'
        obj = CpuUtilizationCgroupSystemProvider(100, folder=GMT_METRICS_DIR, skip_check=True)

    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/cpu_utilization_cgroup_system.log')

    df = obj.read_metrics()

    assert df.metric.unique() == ['cpu_utilization_cgroup_system']
    assert df.detail_name.unique() == 'GMT Overhead'
    assert math.isclose(df.value.mean(), 539.3809, abs_tol=1e-3)

def test_cgroup_container():
    obj = CpuUtilizationCgroupContainerProvider(100, folder=GMT_METRICS_DIR, skip_check=True)

    obj._filename = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/cpu_utilization_cgroup_container.log')

    obj.add_containers(Tests.TEST_MEASUREMENT_CONTAINERS)
    df = obj.read_metrics()

    assert df.metric.unique() == ['cpu_utilization_cgroup_container']
    assert list(df.detail_name.unique()) == ['38d1e484f336c40a6e60e4518915a4e385f62fdddd47994d6adcb4fb294b2ec8', '939f410a21730a2275e91b8a949884f7f426b89e50e8b2ffceca271b6a4573b6']

    assert math.isclose(df.value.mean(), 289.595, abs_tol=1e-3)
