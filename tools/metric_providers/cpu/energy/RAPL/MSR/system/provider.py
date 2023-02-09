#pylint: disable=import-error,wrong-import-position
import sys
import os

if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../../..')

from metric_providers.base import BaseMetricProvider


class CpuEnergyRaplMsrSystemProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="cpu_energy_rapl_msr_system",
            metrics={"time": int, "value": int, "package_id": str},
            resolution=resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )


if __name__ == '__main__':
    import time

    o = CpuEnergyRaplMsrSystemProvider(resolution=100)

    print('Starting to profile')
    o.start_profiling()
    time.sleep(2)
    o.stop_profiling()
    #pylint: disable=protected-access
    print('Done, check ', o._filename)
