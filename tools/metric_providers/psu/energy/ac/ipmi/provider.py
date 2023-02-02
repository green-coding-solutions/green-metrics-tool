# pylint: disable=import-error,wrong-import-position,protected-access,subprocess-popen-preexec-fn,consider-using-with,attribute-defined-outside-init

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
        self._unit = 'W'
        super().__init__()

    def start_profiling(self, containers=None):

        resolution_float = 0.001 * self._resolution

        if self._sudo:
            call_string = f"sudo {self._current_dir}/ipmi-get-system-power-stat.sh -i {resolution_float}"
        else:
            call_string = f"{self._current_dir}/ipmi-get-system-power-stat.sh -i {resolution_float}"
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


if __name__ == '__main__':
    import time
    import argparse

    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    o = PsuEnergyAcIpmiProvider(resolution=100)

    print('Starting to profile')
    o.start_profiling()
    time.sleep(2)
    o.stop_profiling()
    print('Done, check ', o._filename)
