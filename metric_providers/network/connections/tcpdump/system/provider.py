import os
import re
from collections import defaultdict
import ipaddress
# import netifaces # netifaces has been abandoned. Find new implementation TODO

from metric_providers.base import BaseMetricProvider

class NetworkConnectionsTcpdumpSystemProvider(BaseMetricProvider):
    def __init__(self, *_, split_ports=True, skip_check=False):
        super().__init__(
            metric_name='network_connections_tcpdump_system',
            metrics={},
            resolution=None,
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

    def _add_unit_and_metric(self, df):
        return df # noop. Just for overwriting

    def _check_monotonic(self, df):
        pass  # noop. Just for overwriting

    def _check_resolution_underflow(self, df):
        pass  # noop. Just for overwriting

    def _add_and_validate_resolution_and_jitter(self, df):
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

def parse_tcpdump(lines, split_ports=False):
    stats = defaultdict(lambda: {'ports': defaultdict(lambda: {'packets': 0, 'bytes': 0}), 'total_bytes': 0})
    ip_pattern = r'(\S+) > (\S+):'
    #tcp_pattern = r'Flags \[(.+?)\]'

    for line in lines:
        ip_match = re.search(ip_pattern, line)
        #tcp_match = re.search(tcp_pattern, line)

        if ip_match:
            src, dst = ip_match.groups()
            src_ip, src_port = parse_ip_port(src)
            dst_ip, dst_port = parse_ip_port(dst)

            if src_ip and dst_ip:
                protocol = "UDP" if "UDP" in line else "TCP"

                if protocol == "UDP":
                    # For UDP, use the reported length
                    length_pattern = r'length:? (\d+)'
                    length_match = re.search(length_pattern, line)
                    if not length_match or not length_match.group(1):
                        raise RuntimeError(f"Could not find UDP packet length for line: {line}")
                    packet_length = int(length_match.group(1))

                else:
                    # For TCP, estimate packet length (this is a simplification)
                    length_pattern = r'length (\d+)'
                    length_match = re.search(length_pattern, line)

                    if not length_match or not length_match.group(1):
                        if '.53 ' in line or '.53:' in line or '.5353 ' in line or '.5353:' in line: # try DNS / MDNS match
                            dns_packet_length = re.match(r'.*\((\d+)\)$', line)
                            if not dns_packet_length:
                                raise RuntimeError(f"Could not find TCP packet length for line: {line}")
                            packet_length = int(dns_packet_length[1])
                        else:
                            raise RuntimeError(f"No packet length was detected for line {line}")
                    else:
                        packet_length = 40 + int(length_match.group(1))  # Assuming 40 bytes for IP + TCP headers

                # Update source IP stats
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

def parse_ip_port(address):
    try:
        if ']' in address:  # IPv6
            ip, port = address.rsplit('.', 1)
            ip = ip.strip('[]')
        else:  # IPv4
            ip, port = address.rsplit('.', 1)

        # Validate IP address
        ipaddress.ip_address(ip)
        return ip, int(port)
    except ValueError:
        return None, None

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
