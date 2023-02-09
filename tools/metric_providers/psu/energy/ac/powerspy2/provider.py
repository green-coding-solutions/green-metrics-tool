# pylint: disable=import-error,wrong-import-position,protected-access,unused-argument

import sys
import os
import subprocess

if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../../../..')
from metric_providers.base import BaseMetricProvider


class PowerSpy2Provider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="psu_energy_powerspy2",
            metrics={"time": int, "value": int},
            resolution=resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )

    def start_profiling(self, containers=None):
        # We ignore the resolution here as everything under 1 second doesn't really make sense for the powerspy in the
        # mode we are using it. This can be extended in the future once we figure out how to log to a file and don't
        # rely on the "streaming" of data.
        call_string = f"{self._current_dir}/metric-provider.py -u mJ -i {self._resolution}"

        call_string += f" > {self._filename}"

        print(call_string)

        #pylint: disable=subprocess-popen-preexec-fn,consider-using-with,attribute-defined-outside-init
        self._ps = subprocess.Popen(
            [call_string],
            shell=True,
            preexec_fn=os.setsid,
            stderr=subprocess.PIPE
        )

    def get_stderr(self):
        return None


if __name__ == '__main__':
    import time

    o = PowerSpy2Provider(resolution=200)

    print('Starting to profile')
    o.start_profiling()
    time.sleep(10)
    o.stop_profiling()
    print('Done, check ', o._filename)
