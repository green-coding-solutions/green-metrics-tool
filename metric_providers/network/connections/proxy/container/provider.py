# This code handles the setup of the proxy we use to monitor the network connections in the docker containers.
# Structurally it is a copy of the BaseMetricProvider but because we need to do things slightly different it is a copy.
# In the future this might be implemented as a proper provider.

import os
import re
from datetime import datetime, timezone
import platform
import subprocess
from packaging.version import parse
import pandas

from metric_providers.base import MetricProviderConfigurationError, BaseMetricProvider
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

class NetworkConnectionsProxyContainerProvider(BaseMetricProvider):
    def __init__(self, *, folder, host_ip=None, skip_check=False):
        tinyproxy_path = subprocess.getoutput('which tinyproxy')

        super().__init__(
            metric_name='network_connections_proxy_container_dockerproxy',
            metrics={},
            sampling_rate=None,
            unit=None,
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
            metric_provider_executable=f"{tinyproxy_path}",
        )

        self._conf_file = f"{CURRENT_DIR}/proxy_conf.conf"
        self._host_ip = host_ip

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        super().check_system(check_command=None)

        # check tinyproxy version
        output = subprocess.check_output(['tinyproxy', '-v'], stderr=subprocess.STDOUT, encoding='UTF-8', errors='replace')
        version_string = output.strip().split()[1].split('-')[0]
        if parse(version_string) >= parse('1.11'):
            return True

        raise MetricProviderConfigurationError('Tinyproxy needs to be version 1.11 or greater.')


    def get_docker_params(self, no_proxy_list=''):

        proxy_addr = ''
        if self._host_ip:
            proxy_addr = self._host_ip
        elif platform.system() == 'Linux':
            # Under Linux there is no way to directly link to the host
            cmd =  "ip addr show dev $(ip route | grep default | awk '{print $5}') | grep 'inet '| awk '{print $2}'| cut -f1 -d'/'"
            output = subprocess.check_output(cmd, shell=True, encoding='UTF-8', errors='replace')
            proxy_addr = output.strip()
        else:
            proxy_addr = 'host.docker.internal'

        if no_proxy_list == '':
            no_proxy_list = '127.0.0.1,localhost'
        else:
            no_proxy_list = f"{no_proxy_list},127.0.0.1,localhost"

        # See https://about.gitlab.com/blog/2021/01/27/we-need-to-talk-no-proxy/ for a discussion on the env vars
        # To be sure we include all variants
        return ['--env', f"HTTP_PROXY=http://{proxy_addr}:8889",
                '--env', f"HTTPS_PROXY=http://{proxy_addr}:8889",
                '--env', f"http_proxy=http://{proxy_addr}:8889",
                '--env', f"https_proxy=http://{proxy_addr}:8889",
                '--env', f"NO_PROXY={no_proxy_list}",
                '--env', f"no_proxy={no_proxy_list}"]

    def _add_extra_switches(self, call_string):
        return f"{call_string} -d -c {self._conf_file}"

    def _read_metrics(self):
        with open(self._filename, 'r', encoding='utf-8') as file:
            return file.readlines()

    def _parse_metrics(self, df):
        pattern = re.compile(r"CONNECT\s+([A-Za-z]{3} \d{2} \d{2}:\d{2}:\d{2}(?:\.\d{3})?) \[\d+\]: Request \(file descriptor \d+\): (.+) (.+)")

        parsed_lines = []
        for line in df:
            match = pattern.search(line)
            if match:
                date_str, connection_type, protocol = match.groups()
                # parse the date and time
                try:
                    date = datetime.strptime(f"{datetime.now().year} {date_str}", '%Y %b %d %H:%M:%S.%f')
                except ValueError:
                    date = datetime.strptime(f"{datetime.now().year} {date_str}", '%Y %b %d %H:%M:%S')

                time =  int(date.replace(tzinfo=timezone.utc).timestamp() * 1000)
                parsed_lines.append([time, connection_type, protocol])

        return pandas.DataFrame.from_records(parsed_lines, columns=['time', 'connection_type', 'protocol']) # may be empty as no network traffic can happen

    def _check_unique(self, df):
        pass # noop. Just for overwriting. Empty data is ok for this reporter

    def _check_empty(self, df):
        pass # noop. Just for overwriting. Empty data is ok for this reporter

    def _check_monotonic(self, df):
        pass  # noop. Just for overwriting

    def _add_auxiliary_fields(self, df):
        return df # noop. Just for overwriting

    def _check_sampling_rate_underflow(self, df):
        pass  # noop. Just for overwriting

    def _add_and_validate_sampling_rate_and_jitter(self, df):
        return df # noop. Just for overwriting
