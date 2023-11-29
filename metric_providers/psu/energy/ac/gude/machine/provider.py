import os
import subprocess

from metric_providers.base import BaseMetricProvider


class PsuEnergyAcGudeMachineProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='psu_energy_ac_gude_machine',
            metrics={'time': int, 'value': int},
            resolution=resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

    def start_profiling(self, containers=None):
        call_string = f"{self._current_dir}/check_gude_modified.py -i {self._resolution}"

        call_string += f" > {self._filename}"

        print(call_string)

        #pylint:disable=subprocess-popen-preexec-fn,consider-using-with
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
