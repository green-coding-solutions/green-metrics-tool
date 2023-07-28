# pylint: disable=no-member,consider-using-with,subprocess-popen-preexec-fn,import-error,too-many-instance-attributes,too-many-arguments

# This code handles the setup of the proxy we use to monitor the network connections in the docker containers.
# Structurally it is a copy of the BaseMetricProvider but because we need to do things slightly different it is a copy.
# In the future this might be implemented as a proper provider.

import os
from pathlib import Path
import subprocess
import signal
import sys
import time
import re
from datetime import datetime, timezone
import platform
import subprocess
from packaging.version import parse

from db import DB
from global_config import GlobalConfig
from metric_providers.base import MetricProviderConfigurationError
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

class NetworkConnectionsProxyContainerProvider:

    def __init__(self, host_ip=None):
        self._metric_name = 'dockerproxy'
        self._tmp_folder = '/tmp/green-metrics-tool'
        self._conf_file = f"{CURRENT_DIR}/proxy_conf.conf"
        self._filename = f"{self._tmp_folder}/proxy.log"
        self._ps = None
        self._host_ip = host_ip
        self._has_started = False

        Path(self._tmp_folder).mkdir(exist_ok=True)

    # This needs to be static as we want to check the system before we initialise all the providers
    def check_system(self):

        output = subprocess.check_output(["tinyproxy", "-v"], stderr=subprocess.STDOUT, text=True)
        version_string = output.strip().split()[1].split('-')[0]
        if parse(version_string) >= parse("1.11"):
            return True

        raise MetricProviderConfigurationError('Tinyproxy needs to be version 1.11 or greater.')

    def has_started(self):
        return self._has_started

    def get_stderr(self):
        return self._ps.stderr.read()

    def get_docker_params(self):

        if self._host_ip:
            return ['--env', f"HTTP_PROXY=http://{self._host_ip}:8889",
                    '--env', f"HTTPS_PROXY=http://{self._host_ip}:8889"]
        elif platform.system() == 'Linux':
            # Under Linux there is no way to directly link to the host
            cs =  "ip addr show dev $(ip route | grep default | awk '{print $5}') | grep 'inet '| awk '{print $2}'| cut -f1 -d'/'"
            ps = subprocess.run(cs, shell=True, check=True, text=True, capture_output=True)
            return ['--env', f"HTTP_PROXY=http://{ps.stdout.strip()}:8889",
                    '--env', f"HTTPS_PROXY=http://{ps.stdout.strip()}:8889"]
        else:
             return ['--env', 'HTTP_PROXY=http://host.docker.internal:8889',
                     '--env', 'HTTPS_PROXY=http://host.docker.internal:8889']


    def read_metrics(self, project_id, *_):
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

                query = """
                    INSERT INTO network_intercepts (project_id, time, connection_type, protocol)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                    """
                params = (project_id, time, connection_type, protocol)
                DB().fetch_one(query, params=params)
                records_added += 1

        return records_added


    def start_profiling(self, *_):

        call_string = f"tinyproxy -d -c {self._conf_file} > {self._filename}"

        print(call_string)

        self._ps = subprocess.Popen(
            [call_string],
            shell=True,
            preexec_fn=os.setsid,
            stderr=subprocess.PIPE
            # since we are launching the command with shell=True we cannot use ps.terminate() / ps.kill().
            # This would just kill the executing shell, but not it's child and make the process an orphan.
            # therefore we use os.setsid here and later call os.getpgid(pid) to get process group that the shell
            # and the process are running in. These we then can send the signal to and kill them
        )

        # set_block False enables non-blocking reads on stderr.read(). Otherwise it would wait forever on empty
        os.set_blocking(self._ps.stderr.fileno(), False)
        self._has_started = True

    def stop_profiling(self, *_):
        if self._ps is None:
            return
        try:
            print(f"Killing process with id: {self._ps.pid}")
            ps_group_id = os.getpgid(self._ps.pid)
            print(f" and process group {ps_group_id}")
            os.killpg(ps_group_id, signal.SIGTERM)
            try:
                self._ps.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # If the process hasn't gracefully exited after 5 seconds we kill it
                os.killpg(ps_group_id, signal.SIGKILL)

        except ProcessLookupError:
            print(f"Could not find process-group for {self._ps.pid}",
                    file=sys.stderr)  # process/-group may have already closed

        self._ps = None

if __name__ == "__main__":
    pp = ProxyMetricsProvider()
    pp.start_profiling()
    time.sleep(10)
    pp.stop_profiling()
    pp.read_metrics()