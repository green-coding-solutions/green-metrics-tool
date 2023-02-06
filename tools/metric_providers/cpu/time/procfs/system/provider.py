# pylint: disable=import-error,wrong-import-position,protected-access

import sys
import os

if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../..')

from metric_providers.base import BaseMetricProvider


class CpuTimeProcfsSystemProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="cpu_time_procfs_system",
            metrics={"time": int, "value": int},
            resolution=resolution,
            unit="us",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )


if __name__ == '__main__':
    import time

    o = CpuTimeProcfsSystemProvider(resolution=100)

    print('Starting to profile')
    o.start_profiling()
    time.sleep(2)
    o.stop_profiling()
    print('Done, check ', o._filename)
