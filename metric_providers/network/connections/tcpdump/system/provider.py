import os

from metric_providers.base import BaseMetricProvider

class NetworkConnectionsTcpdumpSystemProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='network_connections_tcpdump_system_provider',
            metrics={'time': int, 'value': int},
            resolution=resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable='ipmi-get-machine-energy-stat.sh',
            skip_check=skip_check,
        )


    def read_metrics(self, run_id, containers=None):
        raise NotImplementedError("")
