import sys, os
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../../../..')
from metric_providers.base import BaseMetricProvider

class MemoryEnergyRaplMsrSystemProvider(BaseMetricProvider):
        def __init__(self, resolution):
            self._current_dir = os.path.dirname(os.path.abspath(__file__))
            self._metric_name = "memory_energy_rapl_msr_system"
            self._metrics = {"time":int, "value":int}
            self._resolution = resolution
            self._extra_switches = ['-d']
            super().__init__()

if __name__ == "__main__":
    import time

    o = MemoryEnergySystemRaplMsrProvider(resolution=100)

    print("Starting to profile")
    o.start_profiling()
    time.sleep(2)
    o.stop_profiling()
    print("Done, check ", o._filename)

