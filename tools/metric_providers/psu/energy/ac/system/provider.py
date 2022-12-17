import sys, os
import subprocess

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../../../../..')
from metric_providers.base import BaseMetricProvider

class PsuEnergyAcSystemProvider(BaseMetricProvider):
        def __init__(self, resolution):
            self._current_dir = os.path.dirname(os.path.abspath(__file__))
            self._metric_name = "psu_energy_ac_system"
            self._metrics = {"time":int, "value":int}
            self._resolution = resolution
            self._unit = 'mJ'
            super().__init__()

        def start_profiling(self, containers=None):
            call_string = f"{self._current_dir}/check_gude_modified.py -i {self._resolution}"

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


if __name__ == "__main__":
    import time
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("container_id", help="Please provide the container_id")
    args = parser.parse_args()

    o = PsuEnergyAcSystemProvider(resolution=100)

    print("Starting to profile")
    o.start_profiling()
    time.sleep(2)
    o.stop_profiling()
    print("Done, check ", o._filename)
