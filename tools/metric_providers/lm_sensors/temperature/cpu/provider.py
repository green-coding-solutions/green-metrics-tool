import sys, os
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../../../..')

from metric_providers.base import BaseMetricProvider

class LmSenorsCpuTempProvider(BaseMetricProvider):
        def __init__(self, resolution):
            # This is a little trick we do so that we can share one executable and
            # just pass in different parameters to get different providers
            self._current_dir = os.path.dirname(os.path.abspath(__file__))+'/../..'
            self._extra_switches = ['CPU']

            self._metric_name = "cpu_temperature"
            self._metrics = {"time":int, "value":int}
            self._resolution = resolution

            super().__init__()

if __name__ == "__main__":
    import time

    o = LmSenorsCpuTempProvider(resolution=100)

    print (o._current_dir)
    print("Starting to profile")
    o.start_profiling()
    time.sleep(5)
    o.stop_profiling()
    print("Done, check ", o._filename)

