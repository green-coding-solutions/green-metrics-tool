# pylint: disable=no-member,consider-using-with,subprocess-popen-preexec-fn,import-error,too-many-instance-attributes,too-many-arguments

import os
from pathlib import Path
import subprocess
import signal
import sys
from io import StringIO
import pandas

from lib.system_checks import ConfigurationCheckError

class MetricProviderConfigurationError(ConfigurationCheckError):
    pass

class BaseMetricProvider:

    def __init__(
        self,
        metric_name,
        metrics,
        resolution,
        unit,
        current_dir,
        metric_provider_executable='metric-provider-binary',
        sudo=False,
    ):
        self._metric_name = metric_name
        self._metrics = metrics
        self._resolution = resolution
        self._unit = unit
        self._current_dir = current_dir
        self._metric_provider_executable = metric_provider_executable
        self._sudo = sudo
        self._has_started = False

        self._tmp_folder = '/tmp/green-metrics-tool'
        self._ps = None
        self._extra_switches = []

        Path(self._tmp_folder).mkdir(exist_ok=True)

        self._filename = f"{self._tmp_folder}/{self._metric_name}.log"

    # implemented as getter function and not direct access, so it can be overloaded
    # some child classes might not actually have _ps attribute set
    def get_stderr(self):
        return self._ps.stderr.read()

    def has_started(self):
        return self._has_started

    def read_metrics(self, project_id, containers):
        with open(self._filename, 'r', encoding='utf-8') as file:
            csv_data = file.read()

        # remove the last line from the string, as it may be broken due to the output buffering of the metrics reporter
        csv_data = csv_data[:csv_data.rfind('\n')]

        # pylint: disable=invalid-name
        df = pandas.read_csv(StringIO(csv_data),
                             sep=' ',
                             names=self._metrics.keys(),
                             dtype=self._metrics
                             )

        if self._metrics.get('sensor_name') is not None:
            df['detail_name'] = df.sensor_name
            df = df.drop('sensor_name', axis=1)
        elif self._metrics.get('package_id') is not None:
            df['detail_name'] = df.package_id
            df = df.drop('package_id', axis=1)
        elif self._metrics.get('core_id') is not None:
            df['detail_name'] = df.core_id
            df = df.drop('core_id', axis=1)
        elif self._metrics.get('container_id') is not None:
            df['detail_name'] = df.container_id
            for container_id in containers:
                df.loc[df.detail_name == container_id, 'detail_name'] = containers[container_id]
            df = df.drop('container_id', axis=1)
        else: # We use the default granularity from the name of the provider eg. "..._machine"  => [MACHINE]
            df['detail_name'] = f"[{self._metric_name.split('_')[-1]}]"

        df['unit'] = self._unit
        df['metric'] = self._metric_name
        df['project_id'] = project_id

        return df

    def start_profiling(self, containers=None):

        call_string = f"{self._metric_provider_executable} -i {self._resolution}"

        if self._metric_provider_executable[0] != '/':
            call_string = f"{self._current_dir}/{call_string}"

        if self._sudo:
            call_string = f"sudo {call_string} "

        if hasattr(self, '_extra_switches'):
            call_string += ' '  # space at start
            call_string += ' '.join(self._extra_switches)

        # This needs refactoring see https://github.com/green-coding-berlin/green-metrics-tool/issues/45
        if self._metrics.get('container_id') is not None:
            call_string += ' -s '
            call_string += ','.join(containers.keys())
        call_string += f" > {self._filename}"

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

    def stop_profiling(self):
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
