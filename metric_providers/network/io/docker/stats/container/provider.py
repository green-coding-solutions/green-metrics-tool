import os
import subprocess

from metric_providers.base import BaseMetricProvider

class NetworkIoDockerStatsContainerProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='network_io_docker_stats_container',
            metrics={'time': int, 'value': int, 'container_id': str},
            resolution=resolution,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

    def start_profiling(self, containers=None):
        print('Start profiling Overloaded for docker_stats. This provider is only for testing! \
                Never use in production!')

        #pylint: disable=subprocess-popen-preexec-fn,consider-using-with
        self._ps = subprocess.Popen(
            ["docker stats --no-trunc --format '{{.Name}} - {{.NetIO}}' " +
                ' '.join(containers.keys()) +
                '  > /tmp/green-metrics-tool/docker_stats.log &'],
            shell=True,
            preexec_fn=os.setsid,
            encoding='UTF-8')

    def read_metrics(self, run_id, containers=None):
        print('Read Metrics is overloaded for docker_stats, since values are not time-keyed. \
            Reporter is only for manual falsification. Never use in production!')
