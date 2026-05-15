import os
from datetime import datetime, timezone

import pandas
import requests

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError
from metric_providers.carbon.intensity.helpers import expand_to_sampling_rate


API_LATEST_URL = "https://api.electricitymaps.com/v4/carbon-intensity-level/latest"

LEVEL_MAP = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "very_high": 4,
}


class CarbonIntensityLevelElectricitymapsMachineProvider(BaseMetricProvider):
    def __init__(self, region, token, folder, sampling_rate=-1, skip_check=False):

        self.region = region
        self.token = token
        self._folder = folder
        self._start_time = None
        self._end_time = None

        if not self.region:
            raise MetricProviderConfigurationError(
                'Please set the region config option for CarbonIntensityLevelElectricitymapsMachineProvider in the config.yml')

        if not self.token:
            raise MetricProviderConfigurationError(
                'Please set the token config option for CarbonIntensityLevelElectricitymapsMachineProvider in the config.yml')

        super().__init__(
            metric_name='carbon_intensity_level_electricitymaps_machine',
            metrics={'time': int, 'value': int, 'provider': str},
            sampling_rate=sampling_rate,
            unit='level',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
        )

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        super().check_system(check_command=None, check_parallel_provider=False)

        try:
            with requests.get(
                API_LATEST_URL,
                params={'zone': self.region},
                headers={'auth-token': self.token},
                timeout=10,
            ) as response:
                if response.status_code in (401, 403):
                    raise MetricProviderConfigurationError(
                        'Electricity Maps token was rejected. Please verify the token in the config.yml'
                    )
                if response.status_code != 200:
                    raise MetricProviderConfigurationError(
                        f"Electricity Maps carbon intensity level health check failed with status {response.status_code}: {response.text}"
                    )
        except requests.RequestException as exc:
            raise MetricProviderConfigurationError(f"Electricity Maps base URL {API_LATEST_URL} could not be reached: {exc}") from exc

    def get_stderr(self):
        return None

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

        response = None
        try:
            response = requests.get(
                API_LATEST_URL,
                params={'zone': self.region},
                headers={'auth-token': self.token},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Failed to query Electricity Maps carbon intensity level service: {exc}") from exc
        finally:
            if response is not None:
                response.close()

        if response.status_code != 200:
            raise RuntimeError(f"Electricity Maps carbon intensity level request failed with status {response.status_code}: {response.text}\n")

        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError(f"Unexpected Electricity Maps carbon intensity level response: {payload}\n")

        raw_level = payload.get('data', [{}])[0].get('level')
        if raw_level is None:
            raise RuntimeError(f"carbonIntensityLevel key missing from Electricity Maps response: {payload}\n")

        level_value = LEVEL_MAP.get(str(raw_level).lower().strip(), 0)

        start_us = int(self._start_time.timestamp() * 1_000_000)
        end_us = int(self._end_time.timestamp() * 1_000_000)

        if end_us <= start_us:
            end_us = start_us + 1

        records = [
            {'time': start_us, 'value': level_value, 'provider': 'electricity_maps'},
            {'time': end_us, 'value': level_value, 'provider': 'electricity_maps'},
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
