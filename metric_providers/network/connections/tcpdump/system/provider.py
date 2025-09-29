import os
import re
from collections import defaultdict
import ipaddress
# import netifaces # netifaces has been abandoned. Find new implementation TODO

from metric_providers.base import BaseMetricProvider
from lib import error_helpers

class NetworkConnectionsTcpdumpSystemProvider(BaseMetricProvider):
    def __init__(self, *_, split_ports=True, skip_check=False):
        super().__init__(
            metric_name='network_connections_tcpdump_system',
            metrics={},
            sampling_rate=None,
            unit=None,
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable='tcpdump.sh',
            skip_check=skip_check
        )
        self.split_ports = split_ports


    def _read_metrics(self):
        with open(self._filename, 'r', encoding='utf-8') as file:
            lines = file.readlines()
            if not lines: # a bit of a hack, because we are expecting a dict later and it will get returned prematurely as list if empty
                return {}
            return lines

    def _parse_metrics(self, df):
        return parse_tcpdump(df, split_ports=self.split_ports)

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
        # tcpdump: listening on eno2, link-type EN10MB (Ethernet), snapshot length 262144 bytes
        line_token = stderr.find("\n")
        if line_token and 'tcpdump: data link type' in stderr[:line_token]:
            stderr = stderr[stderr.find("\n")+1:]
        if line_token and 'tcpdump: listening on' in stderr[:line_token]:
            stderr = stderr[stderr.find("\n")+1:]

        return stderr

def get_primary_interface():
    gateways = netifaces.gateways()
    if 'default' in gateways and netifaces.AF_INET in gateways['default']:
        return gateways['default'][netifaces.AF_INET][1]

    raise RuntimeError('Could not get primary network interface')

def get_ip_addresses(interface):
    addresses = []

    try:
        addrs = netifaces.ifaddresses(interface)

        if netifaces.AF_INET in addrs:
            addresses.append(addrs[netifaces.AF_INET][0]['addr'])

        if netifaces.AF_INET6 in addrs:
            # Get the first non-link-local IPv6 address
            for addr in addrs[netifaces.AF_INET6]:
                if not addr['addr'].startswith('fe80:') and not addr['addr'].startswith('fd00:'):
                    addresses.append(addr['addr'])
                    break
    except RuntimeError as e:
        print(f"Error getting IP addresses: {e}")

    if not addresses:
        raise RuntimeError('Could not determine either IPv4 or IPv6 address')

    return addresses

def add_packet_to_stats(stats, src_ip, dst_ip, src_port, dst_port, protocol, packet_length, split_ports):
    if split_ports:
        stats[src_ip]['ports'][f"{src_port}/{protocol}"]['packets'] += 1
        stats[src_ip]['ports'][f"{src_port}/{protocol}"]['bytes'] += packet_length
    else:
        stats[src_ip]['ports'][f"{protocol}"]['packets'] += 1 # alternative without splitting by port
        stats[src_ip]['ports'][f"{protocol}"]['bytes'] += packet_length  # alternative without splitting by port

    stats[src_ip]['total_bytes'] += packet_length

    # Update destination IP stats
    if split_ports:
        stats[dst_ip]['ports'][f"{dst_port}/{protocol}"]['packets'] += 1
        stats[dst_ip]['ports'][f"{dst_port}/{protocol}"]['bytes'] += packet_length
    else:
        stats[dst_ip]['ports'][f"{protocol}"]['packets'] += 1 # alternative without splitting by port
        stats[dst_ip]['ports'][f"{protocol}"]['bytes'] += packet_length  # alternative without splitting by port

    stats[dst_ip]['total_bytes'] += packet_length

    return stats

def parse_tcpdump(lines, split_ports=False):
    stats = defaultdict(lambda: {'ports': defaultdict(lambda: {'packets': 0, 'bytes': 0}), 'total_bytes': 0})
    ethertype_unknown = r'(\S+) > (\S+), ethertype Unknown \(0x\w+\), length (\d+):\s*$'
    time_ip_and_payload_length_pattern = r'\d{10,15}\.\d{6}.*next-header (\w+) \(\d+\) payload length: (\d+)\) (\S+) > (\S+):'
    time_and_protocol_pattern = r'^\d{10,15}\.\d{6}.* proto (\w+).* length (\d+)'
    only_ip_pattern = r'(\S+) > (\S+):'
    lldp_pattern = r'^\d{10,15}\.\d{6} (LLDP), length (\d+)\s*$'

    packet_length = None # running variable
    protocol = None # running variable


    for line in lines:
        try:
            if ethertype_unknown_match := re.search(ethertype_unknown, line):
                #print('Ethermatch', ethertype_unknown_match.groups())
                src, dst, packet_length = ethertype_unknown_match.groups()
                packet_length = int(packet_length)
                src_ip, src_port, dst_ip, dst_port, protocol = 'Unknown Port', 'Unknown Port', 'Unknown Port', 'Unknown Port', 'Unknown Etherframe'
                add_packet_to_stats(stats, src_ip, dst_ip, src_port, dst_port, protocol, packet_length, split_ports)
            elif data_stream_match := re.search(time_ip_and_payload_length_pattern, line):
                #print('data_stream_match', data_stream_match.groups())
                protocol, packet_length, src, dst = data_stream_match.groups()
                packet_length = int(packet_length)
                src_ip, src_port = parse_ip_port(src)
                dst_ip, dst_port = parse_ip_port(dst)
                add_packet_to_stats(stats, src_ip, dst_ip, src_port, dst_port, protocol, packet_length, split_ports)
            elif protocol_match := re.search(time_and_protocol_pattern, line):
                #print('protocol match', protocol_match.groups())
                protocol, packet_length = protocol_match.groups()
                packet_length = int(packet_length)
                continue # we fetch data only in the next line, thus we skip variable reset here

            elif ip_match := re.search(only_ip_pattern, line):
                #print('ip match', ip_match.groups())
                src, dst = ip_match.groups()
                src_ip, src_port = parse_ip_port(src)
                dst_ip, dst_port = parse_ip_port(dst)
                add_packet_to_stats(stats, src_ip, dst_ip, src_port, dst_port, protocol, packet_length, split_ports)
                continue # no reset, as we can have multiple packets following here
            elif lldp_match := re.search(lldp_pattern, line):
                #print('lldp match', lldp_match.groups())
                protocol, packet_length = lldp_match.groups()
                packet_length = int(packet_length)
                src = dst = '-'
                src_ip = src_port = '-'
                dst_ip = dst_port = '-'
                add_packet_to_stats(stats, src_ip, dst_ip, src_port, dst_port, protocol, packet_length, split_ports)
            elif 'tcpdump: listening on' in line:
                continue
            elif 'tcpdump: data link type' in line:
                continue
            elif not line.strip(): # ignore empty lines
                continue
            elif 'ARP, Ethernet' in line: # we ignore ARP for now
                continue
            elif line.startswith('    ') or line.startswith('\t'): # these are all detail infos for specific control packets. 4-6 indents indicate deep detail infos
                continue
            else:
                error_helpers.log_error('Unmatched tcpdump line', line=line, all_lines=lines)
                # this was an exception before. However it seems that tcpdump comes up with unexpected lines ones in a while
                # we have never seen before. Thus this was moved to a log only and will be expanded over time
        except Exception as exc:
            error_helpers.log_error('Exception occured while trying to parse tcdump lines', exception=exc, line=line, all_lines=lines)



        # reset
        packet_length = None
        protocol = None


    return stats

def parse_ip_port(address):
    if ':' in address:  # IPv6
        if address.count('.') < 1: ## no port, which is fine
            port = 0
            ip = address
        elif address.count('.') == 1:
            ip, port = address.rsplit('.', 1)
            ip = ip.strip('[]')
        else:
            raise ValueError(f"Too many ports in address: {address}")

    else:  # IPv4
        if address.count('.') == 3: ## no port, which is fine
            port = 0
            ip = address
        elif address.count('.') == 4:
            ip, port = address.rsplit('.', 1)
        else:
            raise ValueError(f"Unbalanced dots address: {address}")

    # Validate IP address
    ipaddress.ip_address(ip)
    return ip, int(port)

def generate_stats_string(stats, filter_host=False):
    if filter_host:
        raise NotImplementedError('netifaces has been abandoned. A new implementation to enable filter_host is not done yet')
    #primary_interface = get_primary_interface()
    #ip_addresses = get_ip_addresses(primary_interface)

    buffer = []
    for ip, data in stats.items():
        #if filter_host and ip in ip_addresses:
        #    continue

        buffer.append(f"IP: {ip} (as sender or receiver. aggregated)")
        buffer.append(f"  Total transmitted data: {data['total_bytes']} bytes")
        buffer.append('  Ports:')
        for port, port_data in data['ports'].items():
            buffer.append(f"    {port}: {port_data['packets']} packets, {port_data['bytes']} bytes")
        buffer.append('\n')

    return '\n'.join(buffer)
