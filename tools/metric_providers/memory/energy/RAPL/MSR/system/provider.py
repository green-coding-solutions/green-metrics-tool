# pylint: disable=import-error,wrong-import-position,protected-access

import sys
import os

if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../../..')

from metric_providers.base import BaseMetricProvider


class MemoryEnergyRaplMsrSystemProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="memory_energy_rapl_msr_system",
            metrics={'time': int, 'value': int, 'package_id': str},
            resolution=resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )
        self._extra_switches = ['-d']


if __name__ == '__main__':
    import time

    o = MemoryEnergyRaplMsrSystemProvider(resolution=100)

    print('Starting to profile')
    o.start_profiling()
    time.sleep(2)
    o.stop_profiling()
    print('Done, check ', o._filename)
