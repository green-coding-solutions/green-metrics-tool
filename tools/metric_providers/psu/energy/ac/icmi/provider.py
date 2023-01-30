# pylint: disable=import-error,wrong-import-position,protected-access

import sys
import os
import subprocess

if __name__ == '__main__':
    sys.path.append(f'{os.path.dirname(os.path.abspath(__file__))}/../../../../..')

from metric_providers.base import BaseMetricProvider


class PsuEnergyAcIpmiProvider(BaseMetricProvider):
    def __init__(self, resolution):
        self._current_dir = os.path.dirname(os.path.abspath(__file__))
        self._metric_name = 'psu_energy_ac_ipmi'
        self._metrics = {'time': int, 'value': int}
        self._resolution = resolution
        self._unit = 'mJ'
        super().__init__()

    # pylint: disable=unused-argument
    def start_profiling(self, containers=None):
        call_string = f"{self._current_dir}/metric-provider-binary -i {self._resolution}"

        call_string += f" > {self._filename}"

        print(call_string)

        # pylint:disable=subprocess-popen-preexec-fn,consider-using-with,attribute-defined-outside-init
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


if __name__ == '__main__':
    import time
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('container_id', help='Please provide the container_id')
    args = parser.parse_args()

    o = PsuEnergyAcIpmiProvider(resolution=100)

    print('Starting to profile')
    o.start_profiling()
    time.sleep(2)
    o.stop_profiling()
    print('Done, check ', o._filename)
