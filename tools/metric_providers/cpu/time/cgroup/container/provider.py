import sys, os
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../../..')
from metric_providers.base import BaseMetricProvider

class CpuTimeCgroupContainerProvider(BaseMetricProvider):
        def __init__(self, resolution):
            self._current_dir = os.path.dirname(os.path.abspath(__file__))
            self._metric_name = "cpu_time_cgroup_container"
            self._metrics = {"time":int, "value":int, "container_id":str}
            self._resolution = resolution
            self._unit = 'us'
            super().__init__()

if __name__ == "__main__":
    import time
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("container_id", help="Please provide the container_id")
    args = parser.parse_args()

    o = CpuTimeCgroupContainerProvider(resolution=100)

    print("Starting to profile")
    o.start_profiling({args.container_id: "test"})
    time.sleep(2)
    o.stop_profiling()
    print("Done, check ", o._filename)

