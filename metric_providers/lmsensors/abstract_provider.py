# We need to separate the lm sensor providers into multiple files as the frontend has the conversion and
# unit hardcoded. So it is currently not possible to have one provider return temperature and fan speed.
# Discussion is here https://github.com/green-coding-solutions/green-metrics-tool/issues/39

import os
import subprocess
from lib.global_config import GlobalConfig
from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError

class LmsensorsProvider(BaseMetricProvider):

    def _create_options(self):
        provider_config = GlobalConfig().config['measurement']['metric-providers']['linux']\
            [self._provider_config_path]

        if 'chips' not in provider_config:
            raise RuntimeError(
                f"Please set the 'chips' config option for {self._provider_config_path} in the config.yml")
        if 'features' not in provider_config:
            raise RuntimeError(
                f"Please set the 'features' config option for {self._provider_config_path} in the config.yml")

        return ['-c'] + [f"'{i}'" for i in provider_config['chips']] \
            + ['-f'] + [f"'{i}'" for i in provider_config['features']]

    def __init__(self, metric_name, resolution, unit, skip_check=False):
        if __name__ == '__main__':
            # If you run this on the command line you will need to set this in the config
            # This is separate so it is always clear what config is used.
            self._provider_config_path = 'lmsensors.abstract_provider.LmsensorsProvider'


        super().__init__(
            metric_name=metric_name,
            metrics={'time': int, 'value': int, 'sensor_name': str},
            resolution=resolution,
            unit=unit,
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self._extra_switches = self._create_options()

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        super().check_system(check_command=None)

        # Run 'sensors' command and capture the output
        ps = subprocess.run(['sensors'], capture_output=True, text=True, check=False)
        if ps.returncode != 0:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCannot run the 'sensors' command. Did you install lm-sensors?.\n\nAre you running in a VM / cloud / shared hosting?\nIf so please disable the {self._metric_name} provider in the config.yml")

        provider_config = GlobalConfig().config['measurement']['metric-providers']['linux']\
            [self._provider_config_path]

        for config_chip in provider_config['chips']:
            matching_chips = [chip for chip in ps.stdout.split('\n\n') if chip.startswith(config_chip)]

            if not matching_chips:
                raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCannot find a chip starting with '{config_chip}' in output of 'sensors' command.\n\nAre you running in a VM / cloud / shared hosting?\nIf so please disable the {self._metric_name} provider in the config.yml")

            for chip_section in matching_chips:
                for feature in provider_config['features']:
                    if feature not in chip_section:
                        raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCannot find feature '{feature}' in the output section for chip starting with '{config_chip}' of the 'sensors' command.\n\nAre you running in a VM / cloud / shared hosting?\nIf so please disable the {self._metric_name} provider in the config.yml")


    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, containers)

        df['detail_name'] = df.sensor_name
        df = df.drop('sensor_name', axis=1)

        return df
