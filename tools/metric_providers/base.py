import os
import subprocess
import signal
import pandas
from io import StringIO

class BaseMetricProvider:

    def __init__(self, sudo=False):
        self._ps = None
        self._sudo = sudo
        if not hasattr(self, '_metric_name'):
            raise RuntimeError("You must set the _metric_name instance variable in the child class")
        self._filename = f"/tmp/green-metrics-tool/{self._metric_name}.log"

    def read_metrics(self, project_id, containers):
        with open(self._filename, 'r') as f:
            csv_data = f.read()

        csv_data = csv_data[:csv_data.rfind('\n')] # remove the last line from the string, as it may be broken due to the output buffering of the metrics reporter

        df = pandas.read_csv(StringIO(csv_data),
            sep=" ",
            names=self._metrics.keys(),
            dtype=self._metrics
        )

        if self._metrics.get('container_id') is None:
            df['container_name'] = '[SYSTEM]' # standard container name when only system was measured
        else:
            df['container_name'] = df.container_id
            for container_id in containers:
                df.loc[df.container_name == container_id, 'container_name'] = containers[container_id]
            df = df.drop('container_id', axis=1)

        df['metric'] = self._metric_name
        df['project_id'] = project_id

        return df

    def start_profiling(self, containers=None):
        if self._sudo:
            call_string = f"sudo {self._current_dir}/metric-provider-binary -i {self._resolution}"
        else:
            call_string = f"{self._current_dir}/metric-provider-binary -i {self._resolution}"
        if hasattr(self, '_extra_switches'):
             call_string += " " # space at start
             call_string += " ".join(self._extra_switches)

        if self._metrics.get('container_id') is not None:
             call_string += " -s "
             call_string += ",".join(containers.keys())
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

    def stop_profiling(self):
        if self._ps is None: return
        try:
            print(f"Killing process with id: {self._ps.pid}")
            ps_group_id = os.getpgid(self._ps.pid)
            print(f" and process group {ps_group_id}")
            os.killpg(os.getpgid(self._ps.pid), signal.SIGTERM)
        except ProcessLookupError:
            print(f"Could not find process-group for {ps['pid']}", file=sys.stderr) # process/-group may have already closed

        self._ps = None
