import sys, os
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../../../..')
from metric_providers.base import BaseMetricProvider

class EnergyRaplMsrSystemProvider(BaseMetricProvider):
        def __init__(self, resolution):
            self._current_dir = os.path.dirname(os.path.abspath(__file__))
            self._metric_name = "energy_RAPL_MSR_system"
            self._metrics = {"time":int, "value":int}
            self._use_containers = False
            self._resolution = resolution
            super().__init__(sudo=True)

if __name__ == "__main__":
    import time

    o = EnergySystemRaplMsrProvider(resolution=100)

    print("Starting to profile")
    o.start_profiling()
    time.sleep(2)
    o.stop_profiling()
    print("Done, check ", o._filename)

