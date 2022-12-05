import sys, os
import subprocess

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../../../../..')
from metric_providers.base import BaseMetricProvider

class PowerSpy2Provider(BaseMetricProvider):
        def __init__(self, resolution):
            self._current_dir = os.path.dirname(os.path.abspath(__file__))
            self._metric_name = "psu_energy_powerspy2"
            self._metrics = {"time":int, "value":int}
            self._resolution = resolution
            super().__init__()

        def start_profiling(self, containers=None):
            call_string = f"{self._current_dir}/metric-provider.py -i {self._resolution}"

            call_string += f" > {self._filename}"

            print(call_string)

            self._ps = subprocess.Popen(
                [call_string],
                shell=True,
                preexec_fn=os.setsid,
                stderr=subprocess.PIPE
            )

        def get_stderr(self):
            return None


if __name__ == "__main__":
    import time

    o = PowerSpy2Provider(resolution=200)

    print("Starting to profile")
    o.start_profiling()
    time.sleep(10)
    o.stop_profiling()
    print("Done, check ", o._filename)
