import sys, os
import subprocess
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../../../..')
from metric_providers.base import BaseMetricProvider

class NetworkIoDockerStatsContainerProvider(BaseMetricProvider):
        def __init__(self, resolution, extra_switches = ""):
            self._current_dir = os.path.dirname(os.path.abspath(__file__))
            self._metric_name = "network_io_docker_stats_container"
            self._metrics = {"time":int, "value":int, "container_id":str}
            self._resolution = resolution
            self._extra_switches = extra_switches
            super().__init__()

        def start_profiling(self, containers=None):
            print("Start profiling Overloaded for docker_stats. This provider is only for testing! Never use in production!")
            self._ps = subprocess.Popen(
                ["docker stats --no-trunc --format '{{.Name}} - {{.NetIO}}' " + ' '.join(containers.keys()) + "  > /tmp/green-metrics-tool/docker_stats.log &"],
                shell=True,
                preexec_fn=os.setsid,
                encoding="UTF-8"
            )

        def read_metrics(self, project_id, containers):
            print("Read Metrics is overloaded for docker_stats, since values are not time-keyed. Reporter is only for manual falsification. Never use in production!")

if __name__ == "__main__":
    import time
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("container_id", help="Please provide the container_id")
    args = parser.parse_args()

    o = NetworkIoDockerStatsContainerProvider(resolution=100)

    print("Starting to profile")
    o.start_profiling({args.container_id: "test-name"})
    time.sleep(20)
    o.stop_profiling()
    print("Done, check ", o._filename)

