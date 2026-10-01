import os
import math
import functools
import pytest
import shutil
import tempfile
import warnings
import plistlib
import pandas

from pathlib import Path
from xml.parsers.expat import ExpatError
from xml.parsers.expat import errors as expat_errors

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

POWERMETRICS_LOG = os.path.join(GMT_ROOT_DIR, './tests/data/metrics/powermetrics.log')
POWERMETRICS_COLUMNS = ['time', 'value', 'metric', 'unit', 'detail_name', 'sampling_rate_95p']
_EX_CODES = getattr(expat_errors, 'codes')


def _expat_code(error_name):
    # pyexpat.errors is a C extension; attribute names are resolved at runtime.
    return _EX_CODES[getattr(expat_errors, error_name)]


def _powermetrics_fragments():
    payload = Path(POWERMETRICS_LOG).read_bytes()
    fragments = payload.split(b'\x00')
    # The checked-in capture is 34 complete plists with no trailing NUL separator.
    assert b'\x00'.join(fragments) == payload
    assert not payload.endswith(b'\x00')
    assert len(fragments) == 34
    assert all(fragment.endswith(b'</plist>\n') for fragment in fragments)
    return fragments


def _powermetrics_provider(log_path):
    # pgrep would otherwise depend on whatever powermetrics processes the host has.
    with patch.object(PowermetricsProvider, 'powermetrics_total_count', return_value=0):
        provider = PowermetricsProvider(499, folder=GMT_METRICS_DIR, skip_check=True)
    provider._filename = os.fspath(log_path)
    return provider


def _write_powermetrics_capture(directory, name, payload):
    path = Path(directory) / name
    path.write_bytes(payload)
    return path


def _read_powermetrics(log_path):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        dataframe = _powermetrics_provider(log_path).read_metrics()
    truncation_warnings = [
        str(item.message)
        for item in caught
        if issubclass(item.category, RuntimeWarning) and 'truncated final powermetrics sample' in str(item.message)
    ]
    return dataframe, truncation_warnings


@functools.lru_cache(maxsize=4)
def _cached_powermetrics_read(payload):
    with tempfile.TemporaryDirectory(prefix='powermetrics-cache-') as directory:
        path = Path(directory) / 'capture.log'
        path.write_bytes(payload)
        dataframe, truncation_warnings = _read_powermetrics(path)
    return dataframe.copy(), tuple(truncation_warnings)


def _assert_same_powermetrics(left, right):
    assert set(POWERMETRICS_COLUMNS) <= set(left.columns)
    assert set(POWERMETRICS_COLUMNS) <= set(right.columns)
    pandas.testing.assert_frame_equal(
        left.reset_index(drop=True),
        right.reset_index(drop=True),
        check_exact=True,
    )


def _truncate_final_powermetrics_fragment(fragment, kind):
    # Cuts are chosen at specific plist boundaries. Other byte offsets can raise
    # a different Expat code and must not be assumed recoverable.
    if kind == 'xml_tag':
        tag_at = fragment.rfind(b'<key>')
        assert tag_at > 0
        return fragment[:tag_at + 2]
    if kind == 'text':
        text_at = fragment.rfind(b'<string>')
        assert text_at > 0
        return fragment[:text_at + len(b'<string>') + 2]
    if kind == 'closing_document':
        closing_at = fragment.rfind(b'</plist>')
        assert closing_at > 0
        return fragment[:closing_at]
    if kind == 'trim_20':
        return fragment[:-20]
    if kind == 'trim_100':
        return fragment[:-100]
    if kind == 'partial_character':
        text_at = fragment.rfind(b'<string>')
        assert text_at > 0
        return fragment[:text_at + len(b'<string>')] + b'\xc3'
    if kind == 'unclosed_cdata':
        text_at = fragment.rfind(b'<string>')
        assert text_at > 0
        return fragment[:text_at] + b'<string><![CDATA[abc'
    raise ValueError(kind)


def test_powermetrics():
    obj = _powermetrics_provider(POWERMETRICS_LOG)

    df = obj.read_metrics()

    assert list(df.metric.unique()) == ['cpu_time_powermetrics_vm', 'disk_io_bytesread_powermetrics_vm', 'disk_io_byteswritten_powermetrics_vm', 'energy_impact_powermetrics_vm', 'cores_energy_powermetrics_component', 'gpu_energy_powermetrics_component', 'ane_energy_powermetrics_component']

    assert math.isclose(df[df.metric == 'energy_impact_powermetrics_vm'].value.mean(), 430.823529, abs_tol=1e-3)


def test_powermetrics_complete_final_plist_without_trailing_nul_is_kept(tmp_path):
    fragments = _powermetrics_fragments()
    intact_df, intact_warnings = _read_powermetrics(
        _write_powermetrics_capture(tmp_path, 'intact.log', b'\x00'.join(fragments))
    )
    prefix_df, prefix_warnings = _cached_powermetrics_read(b'\x00'.join(fragments[:-1]))
    original_df, original_warnings = _read_powermetrics(POWERMETRICS_LOG)

    assert intact_warnings == []
    assert not prefix_warnings
    assert original_warnings == []
    assert len(intact_df) > len(prefix_df)
    assert intact_df['time'].max() > prefix_df['time'].max()
    _assert_same_powermetrics(intact_df, original_df)


def test_powermetrics_single_trailing_nul_is_not_a_lost_sample(tmp_path):
    fragments = _powermetrics_fragments()
    trailing_df, trailing_warnings = _read_powermetrics(
        _write_powermetrics_capture(tmp_path, 'trailing.log', b'\x00'.join(fragments) + b'\x00')
    )
    original_df, original_warnings = _read_powermetrics(POWERMETRICS_LOG)

    assert trailing_warnings == []
    assert original_warnings == []
    _assert_same_powermetrics(trailing_df, original_df)


@pytest.mark.parametrize('kind, error_name', [
    ('xml_tag', 'XML_ERROR_UNCLOSED_TOKEN'),
    ('text', 'XML_ERROR_NO_ELEMENTS'),
    ('closing_document', 'XML_ERROR_NO_ELEMENTS'),
    ('trim_20', 'XML_ERROR_UNCLOSED_TOKEN'),
    ('trim_100', 'XML_ERROR_NO_ELEMENTS'),
    ('partial_character', 'XML_ERROR_PARTIAL_CHAR'),
    ('unclosed_cdata', 'XML_ERROR_UNCLOSED_CDATA_SECTION'),
])
def test_powermetrics_discards_only_truncated_final_sample(kind, error_name, tmp_path, capsys):
    fragments = _powermetrics_fragments()
    truncated = _truncate_final_powermetrics_fragment(fragments[-1], kind)
    with pytest.raises(ExpatError) as exc_info:
        plistlib.loads(truncated)
    assert exc_info.value.code == _expat_code(error_name)

    recovered, truncation_warnings = _read_powermetrics(
        _write_powermetrics_capture(tmp_path, 'truncated.log', b'\x00'.join(fragments[:-1] + [truncated]))
    )
    prefix_df, prefix_warnings = _cached_powermetrics_read(b'\x00'.join(fragments[:-1]))
    full_df, full_warnings = _cached_powermetrics_read(b'\x00'.join(fragments))
    captured = capsys.readouterr()

    expected_warning = f"Discarding truncated final powermetrics sample {len(fragments)} of {len(fragments)}."
    assert truncation_warnings == [expected_warning]
    assert not prefix_warnings
    assert not full_warnings
    assert '<?xml' not in expected_warning
    assert '<?xml' not in captured.out
    assert '<?xml' not in captured.err
    assert 'com.docker.docker' not in captured.out
    assert 'com.docker.docker' not in captured.err
    _assert_same_powermetrics(recovered, prefix_df)
    assert len(full_df) > len(recovered)
    assert recovered['time'].max() == prefix_df['time'].max()
    assert recovered['time'].max() < full_df['time'].max()


def test_powermetrics_truncated_middle_fragment_raises(tmp_path):
    fragments = _powermetrics_fragments()
    middle = _truncate_final_powermetrics_fragment(fragments[1], 'trim_100')
    with pytest.raises(ExpatError) as exc_info:
        plistlib.loads(middle)
    # Same observed EOF code that a final-fragment trim of 100 bytes recovers from.
    assert exc_info.value.code == _expat_code('XML_ERROR_NO_ELEMENTS')

    payload = b'\x00'.join([fragments[0], middle, fragments[2]])
    provider = _powermetrics_provider(_write_powermetrics_capture(tmp_path, 'middle.log', payload))
    with pytest.raises(ExpatError) as exc_info:
        provider.read_metrics()
    assert exc_info.value.code == _expat_code('XML_ERROR_NO_ELEMENTS')


def test_powermetrics_empty_interior_fragment_raises(tmp_path):
    fragments = _powermetrics_fragments()
    payload = b'\x00'.join([fragments[0], b'', fragments[2]])
    provider = _powermetrics_provider(_write_powermetrics_capture(tmp_path, 'empty-interior.log', payload))
    with pytest.raises(plistlib.InvalidFileException):
        provider.read_metrics()


def test_powermetrics_corrupt_complete_final_plist_raises(tmp_path):
    fragments = _powermetrics_fragments()
    corrupted = fragments[-1].replace(b'<key>gpu_energy</key>', b'<key>gpu_energy &</key>', 1)
    assert corrupted != fragments[-1]
    assert corrupted.rstrip().endswith(b'</plist>')
    with pytest.raises(ExpatError) as exc_info:
        plistlib.loads(corrupted)
    assert exc_info.value.code == _expat_code('XML_ERROR_INVALID_TOKEN')

    payload = b'\x00'.join([fragments[0], corrupted])
    provider = _powermetrics_provider(_write_powermetrics_capture(tmp_path, 'corrupt-final.log', payload))
    with pytest.raises(ExpatError) as exc_info:
        provider.read_metrics()
    assert exc_info.value.code == _expat_code('XML_ERROR_INVALID_TOKEN')


def test_powermetrics_mismatched_tag_final_fragment_raises(tmp_path):
    fragments = _powermetrics_fragments()
    closing_at = fragments[-1].rfind(b'</plist>')
    mismatched = fragments[-1][:closing_at] + b'</dict>\n'
    with pytest.raises(ExpatError) as exc_info:
        plistlib.loads(mismatched)
    assert exc_info.value.code == _expat_code('XML_ERROR_TAG_MISMATCH')

    payload = b'\x00'.join([fragments[0], mismatched])
    provider = _powermetrics_provider(_write_powermetrics_capture(tmp_path, 'mismatched.log', payload))
    with pytest.raises(ExpatError) as exc_info:
        provider.read_metrics()
    assert exc_info.value.code == _expat_code('XML_ERROR_TAG_MISMATCH')


def test_powermetrics_lone_truncated_sample_raises(tmp_path):
    fragments = _powermetrics_fragments()
    truncated = _truncate_final_powermetrics_fragment(fragments[0], 'trim_100')
    with pytest.raises(ExpatError) as exc_info:
        plistlib.loads(truncated)
    assert exc_info.value.code == _expat_code('XML_ERROR_NO_ELEMENTS')

    provider = _powermetrics_provider(_write_powermetrics_capture(tmp_path, 'lone.log', truncated))
    with pytest.raises(ExpatError) as exc_info:
        provider.read_metrics()
    assert exc_info.value.code == _expat_code('XML_ERROR_NO_ELEMENTS')


def test_powermetrics_empty_input_keeps_read_metrics_empty_failure(tmp_path):
    provider = _powermetrics_provider(_write_powermetrics_capture(tmp_path, 'empty.log', b''))
    with pytest.raises(RuntimeError) as exc_info:
        provider.read_metrics()
    assert str(exc_info.value) == 'Metrics provider powermetrics seems to have not produced any measurements. Metrics log file was empty. Either consider having a higher sample rate or turn off provider.'


def test_powermetrics_missing_required_keys_raise(tmp_path):
    fragments = _powermetrics_fragments()

    missing_elapsed = plistlib.loads(fragments[-1])
    del missing_elapsed['elapsed_ns']
    elapsed_plist = plistlib.dumps(missing_elapsed)
    assert 'elapsed_ns' not in plistlib.loads(elapsed_plist)
    elapsed_provider = _powermetrics_provider(
        _write_powermetrics_capture(tmp_path, 'missing-elapsed.log', b'\x00'.join([fragments[0], elapsed_plist]))
    )
    with pytest.raises(KeyError, match='elapsed_ns'):
        elapsed_provider.read_metrics()

    missing_timestamp = plistlib.loads(fragments[0])
    del missing_timestamp['timestamp']
    timestamp_plist = plistlib.dumps(missing_timestamp)
    assert 'timestamp' not in plistlib.loads(timestamp_plist)
    timestamp_provider = _powermetrics_provider(
        _write_powermetrics_capture(tmp_path, 'missing-timestamp.log', timestamp_plist)
    )
    with pytest.raises(KeyError, match='timestamp'):
        timestamp_provider.read_metrics()

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
