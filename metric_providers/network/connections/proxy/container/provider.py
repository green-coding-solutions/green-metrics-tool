# This code handles the setup of the proxy we use to monitor the network connections in the docker containers.
# Structurally it is a copy of the BaseMetricProvider but because we need to do things slightly different it is a copy.
# In the future this might be implemented as a proper provider.

import os
import re
from datetime import datetime, timezone
import platform
import subprocess
from packaging.version import parse

from lib.db import DB
from metric_providers.base import MetricProviderConfigurationError, BaseMetricProvider
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

class NetworkConnectionsProxyContainerProvider(BaseMetricProvider):
    def __init__(self, *, host_ip=None, skip_check=False):
        tinyproxy_path = subprocess.getoutput('which tinyproxy')

        super().__init__(
            metric_name='network_connections_proxy_container_dockerproxy',
            metrics={},
            resolution=None,
            unit=None,
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            metric_provider_executable=f"{tinyproxy_path}",
        )

        self._conf_file = f"{CURRENT_DIR}/proxy_conf.conf"
        self._extra_switches = ['-d', '-c', self._conf_file]
        self._host_ip = host_ip

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        super().check_system(check_command=None)

        # check tinyproxy version
        output = subprocess.check_output(['tinyproxy', '-v'], stderr=subprocess.STDOUT, text=True)
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
            ps = subprocess.run(cmd, shell=True, check=True, text=True, capture_output=True)
            proxy_addr = ps.stdout.strip()
        else:
            proxy_addr = 'host.docker.internal'

        # See https://about.gitlab.com/blog/2021/01/27/we-need-to-talk-no-proxy/ for a discussion on the env vars
        # To be sure we include all variants
        return ['--env', f"HTTP_PROXY=http://{proxy_addr}:8889",
                '--env', f"HTTPS_PROXY=http://{proxy_addr}:8889",
                '--env', f"http_proxy=http://{proxy_addr}:8889",
                '--env', f"https_proxy=http://{proxy_addr}:8889",
                '--env', f"NO_PROXY={no_proxy_list}",
                '--env', f"no_proxy={no_proxy_list}"]


    def read_metrics(self, run_id, containers=None):
        records_added = 0
        with open(self._filename, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        pattern = re.compile(r"CONNECT\s+([A-Za-z]{3} \d{2} \d{2}:\d{2}:\d{2}(?:\.\d{3})?) \[\d+\]: Request \(file descriptor \d+\): (.+) (.+)")

        for line in lines:
            match = pattern.search(line)
            if match:
                date_str, connection_type, protocol = match.groups()
                # parse the date and time
                try:
                    date = datetime.strptime(date_str, '%b %d %H:%M:%S.%f').replace(year=datetime.now().year)
                except ValueError:
                    date = datetime.strptime(date_str, '%b %d %H:%M:%S').replace(year=datetime.now().year)

                time =  int(date.replace(tzinfo=timezone.utc).timestamp() * 1000)

                query = '''
                    INSERT INTO network_intercepts (run_id, time, connection_type, protocol)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    '''
                params = (run_id, time, connection_type, protocol)
                DB().fetch_one(query, params=params)
                records_added += 1

        return records_added
