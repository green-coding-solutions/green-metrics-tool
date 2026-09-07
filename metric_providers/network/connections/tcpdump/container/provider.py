import os
import re
import subprocess

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError
from metric_providers.network.connections.tcpdump.system.provider import parse_tcpdump

# tcpdump -i any (LINUX_SLL2) prefixes every captured line with the source interface name and
# direction, e.g. "1725450000.123456 veth1234a5b6 In  IP 172.17.0.2.54321 > 172.17.0.3.80: ..."
IFACE_PREFIX_PATTERN = re.compile(r'^(?P<ts>\d{10,15}\.\d{6}) (?P<iface>\S+)\s+(?:In|Out|P)\s+(?P<rest>.*)$')


class NetworkConnectionsTcpdumpContainerProvider(BaseMetricProvider):
    def __init__(self, *, folder, split_ports=True, skip_check=False):
        super().__init__(
            metric_name='network_connections_tcpdump_container',
            metrics={},
            sampling_rate=None,
            unit=None,
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable='tcpdump.sh',
            skip_check=skip_check,
            folder=folder,
        )
        self.split_ports = split_ports
        self._interface_to_detail_name = {}

    def add_containers(self, containers):
        for container_id, container_data in containers.items():
            for iface in _resolve_veths(container_id):
                self._interface_to_detail_name[iface] = container_data['name']

    def _add_extra_switches(self, call_string):
        if not self._interface_to_detail_name:
            raise MetricProviderConfigurationError(
                'network_connections_tcpdump_container was started without any resolved container interfaces. '
                'add_containers() must be called before start_profiling().'
            )
        ifname_filter = ' or '.join(f"ifname {iface}" for iface in self._interface_to_detail_name)
        return f"{call_string} -f '{ifname_filter}'"

    def _read_metrics(self):
        with open(self._filename, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            if not lines: # a bit of a hack, because we are expecting a dict later and it will get returned prematurely as list if empty
                return {}
            return lines

    def _parse_metrics(self, df):
        # Strip the per-line interface prefix, regroup lines by owning container, and hand each
        # group to the existing parse_tcpdump() unchanged - this reuses all its regex logic
        # instead of duplicating it.
        #
        # tcpdump -v output is not one line per packet: a packet's header line (which carries the
        # interface prefix) can be followed by indented continuation/detail lines that carry no
        # prefix of their own. Those belong to whichever packet/container the preceding prefixed
        # line resolved to, so we track that as we go rather than dropping unprefixed lines.
        lines_by_container = {}
        current_detail_name = None
        for line in df:
            match = IFACE_PREFIX_PATTERN.match(line)
            if match:
                iface = match.group('iface')
                current_detail_name = self._interface_to_detail_name.get(iface)
                if current_detail_name is None:
                    continue # traffic on an interface we didn't ask for - shouldn't happen given the ifname filter
                lines_by_container.setdefault(current_detail_name, []).append(f"{match.group('ts')} {match.group('rest')}\n")
            elif current_detail_name is not None:
                # continuation/detail line for the packet currently being read - same container
                lines_by_container[current_detail_name].append(line)

        return {
            detail_name: parse_tcpdump(container_lines, split_ports=self.split_ports)
            for detail_name, container_lines in lines_by_container.items()
        }

    def _check_unique(self, df):
        pass # noop. Just for overwriting. Empty data is ok for this reporter

    def _check_empty(self, df):
        pass # noop. Just for overwriting. Empty data is ok for this reporter

    def _add_auxiliary_fields(self, df):
        return df # noop. Just for overwriting

    def _check_monotonic(self, df):
        pass  # noop. Just for overwriting

    def _check_sampling_rate_underflow(self, df):
        pass  # noop. Just for overwriting

    def _add_and_validate_sampling_rate_and_jitter(self, df):
        return df  # noop. Just for overwriting

    def get_stderr(self):
        stderr = super().get_stderr()

        if not stderr:
            return stderr

        # truncate the first two bogus line with information similar to:
        # tcpdump: listening on any, link-type LINUX_SLL2 (Linux cooked v2), snapshot length 262144 bytes
        line_token = stderr.find("\n")
        if line_token and 'tcpdump: data link type' in stderr[:line_token]:
            stderr = stderr[stderr.find("\n")+1:]
        if line_token and 'tcpdump: listening on' in stderr[:line_token]:
            stderr = stderr[stderr.find("\n")+1:]

        return stderr


def _resolve_veths(container_id):
    # Docker does not expose the host-side veth name for a container anywhere in its API/inspect
    # output - it's a kernel-level detail. We use 'docker exec' (rather than nsenter on the host)
    # to read the container's own interfaces and their iflink (peer ifindex) from inside its
    # network namespace, so the docker daemon - which already has the required privileges -
    # performs the namespace entry for us, instead of requiring CAP_SYS_ADMIN/sudo on the host.
    container_ifaces = subprocess.check_output(
        ['docker', 'exec', container_id, 'ls', '/sys/class/net'],
        encoding='UTF-8', errors='replace',
    ).split()

    veths = []
    for iface in container_ifaces:
        if iface == 'lo':
            continue

        peer_index = subprocess.check_output(
            ['docker', 'exec', container_id, 'cat', f'/sys/class/net/{iface}/iflink'],
            encoding='UTF-8', errors='replace',
        ).strip()

        veths.append(_find_host_veth_by_ifindex(peer_index, container_id, iface))

    return veths


def _find_host_veth_by_ifindex(peer_index, container_id, container_iface):
    for host_iface in os.listdir('/sys/class/net'):
        if not host_iface.startswith('veth'):
            continue
        with open(f'/sys/class/net/{host_iface}/ifindex', encoding='utf-8') as file:
            if file.read().strip() == peer_index:
                return host_iface

    raise MetricProviderConfigurationError(
        f"Could not resolve host veth interface for container {container_id} interface {container_iface} (peer ifindex {peer_index})."
    )
