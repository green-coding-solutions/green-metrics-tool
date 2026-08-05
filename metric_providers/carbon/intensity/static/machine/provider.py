import os
from datetime import datetime, timezone

import pandas

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError
from metric_providers.carbon.intensity.helpers import expand_to_sampling_rate


class CarbonIntensityStaticMachineProvider(BaseMetricProvider):
    def __init__(self, *, value, folder, sampling_rate=-1, skip_check=False):

        if value is None:
            raise MetricProviderConfigurationError(
                'Please set the value config option for CarbonIntensityStaticMachineProvider in the config.yml')

        try:
            self.value = float(value)
        except (TypeError, ValueError) as exc:
            raise MetricProviderConfigurationError(
                f'value for CarbonIntensityStaticMachineProvider must be numeric (got {value!r})') from exc

        self._folder = folder
        self._start_time = None
        self._end_time = None

        super().__init__(
            metric_name='carbon_intensity_static_machine',
            metrics={'time': int, 'value': int, 'provider': str},
            sampling_rate=sampling_rate,
            unit='gCO2e/kWh',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
        )

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        # No external system to verify for a statically configured value
        return True

    def get_stderr(self):
        return ''

    def start_profiling(self, _=None):
        self._start_time = datetime.now(timezone.utc)
        self._has_started = True

    def stop_profiling(self):
        self._end_time = datetime.now(timezone.utc)
        self._has_started = False

    def _read_metrics(self):
        if self._start_time is None or self._end_time is None:
            raise RuntimeError(
                f"{self._metric_name} provider did not record start/end times. Did start_profiling and stop_profiling run?")

        start_us = int(self._start_time.timestamp() * 1_000_000)
        end_us = int(self._end_time.timestamp() * 1_000_000)

        if end_us <= start_us:
            end_us = start_us + 1

        rounded_value = int(round(self.value))

        records = [
            {'time': start_us, 'value': rounded_value, 'provider': 'static'},
            {'time': end_us, 'value': rounded_value, 'provider': 'static'},
        ]

        df = pandas.DataFrame.from_records(records)
        df['value'] = df['value'].astype('int64')
        df = expand_to_sampling_rate(self, df)

        return df

    def _parse_metrics(self, df):
        df['detail_name'] = df['provider']
        df = df.drop(columns=['provider'])
        return df

    def _add_and_validate_sampling_rate_and_jitter(self, df):
        return df
