import os
from datetime import datetime, timezone

import pandas
import requests

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError


class CarbonIntensityElephantMachineProvider(BaseMetricProvider):
    def __init__(self, *, region, elephant, simulation_uuid=None, provider=None, skip_check=False):

        self.region = region
        self.provider_filter = provider
        self.elephant = elephant or {}
        self.simulation_uuid = simulation_uuid
        self.__start_time = None
        self.__end_time = None
        self._elephant_base_url = None
        self.error_string = ""

        if not self.region:
            raise MetricProviderConfigurationError(
                'Please set the region config option for CarbonIntensityElephantMachineProvider in the config.yml')

        if not isinstance(self.elephant, dict):
            raise MetricProviderConfigurationError(
                'Please set the elephant config block for CarbonIntensityElephantMachineProvider in the config.yml')

        host = self.elephant.get('host')
        port = self.elephant.get('port')
        protocol = self.elephant.get('protocol')

        if not host or port is None or not protocol:
            raise MetricProviderConfigurationError(
                'Please set elephant.host, elephant.port, and elephant.protocol for CarbonIntensityElephantMachineProvider in the config.yml')

        self._elephant_base_url = f"{protocol}://{host}:{port}"

        super().__init__(
            metric_name='carbon_intensity_elephant_machine',
            metrics={'time': int, 'value': int, 'provider': str},
            sampling_rate=-1,
            unit='gCO2e/kWh',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        super().check_system(check_command=None, check_parallel_provider=False)
        try:
            response = requests.get(self._elephant_base_url, timeout=10)
            response.close()
        except requests.RequestException as exc:
            raise MetricProviderConfigurationError(
                f"Elephant base URL {self._elephant_base_url} could not be reached: {exc}") from exc

    def get_stderr(self):
        return self.error_string

    def start_profiling(self, _=None):
        self.__start_time = datetime.now(timezone.utc)
        self._has_started = True

    def stop_profiling(self):
        self.__end_time = datetime.now(timezone.utc)
        self._has_started = False

    def _format_time(self, timestamp):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')

    def _parse_time(self, time_value):
        try:
            if time_value.endswith('Z'):
                parsed = datetime.fromisoformat(time_value.replace('Z', '+00:00'))
            else:
                parsed = datetime.fromisoformat(time_value)
        except ValueError as exc:
            raise RuntimeError(f"Invalid time in Elephant response: {time_value}") from exc

        return int(parsed.timestamp() * 1_000_000)

    def _read_metrics(self):
        if self.__start_time is None or self.__end_time is None:
            raise RuntimeError(
                f"{self._metric_name} provider did not record start/end times. Did start_profiling and stop_profiling run?")

        params = {
            'region': self.region,
            'startTime': self._format_time(self.__start_time),
            'endTime': self._format_time(self.__end_time),
            'update': 'true',
        }

        if self.provider_filter:
            params['provider'] = f"{self.provider_filter.lower()}_{self.region.lower()}"

        if self.simulation_uuid:
            params['simulation_id'] = str(self.simulation_uuid)

        url = f"{self._elephant_base_url}/carbon-intensity/history"
        try:
            response = requests.get(url, params=params, timeout=30)
        except requests.RequestException as exc:
            self.error_string += f"Failed to query Elephant carbon intensity service: {exc}\n"
            return None

        if response.status_code != 200:
            self.error_string += f"Elephant carbon intensity request failed with status {response.status_code}: {response.text}\n"
            return None

        data = response.json()

        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected Elephant response for carbon intensity: {data}")

        if len(data) == 0:
            # As the provicers take quite some time to provide data (5 min to 1 hour) it can happen that short running
            # jobs don't have any data. So we just get the most current data point as a fallback.
            if self.provider_filter:
                fallback_url = f"{self._elephant_base_url}/carbon-intensity/current"
            else:
                fallback_url = f"{self._elephant_base_url}/carbon-intensity/current/primary"

            try:
                fallback_response = requests.get(fallback_url, params={'region': self.region}, timeout=30)

                if fallback_response.status_code != 200:
                    self.error_string += f"Elephant carbon intensity fallback request failed with status {fallback_response.status_code}: {fallback_response.text}\n"
                    return None

                data = fallback_response.json()

                if self.provider_filter:
                    data = [d for d in data if d.get('provider') == f"{self.provider_filter.lower()}_{self.region.lower()}"]

            except requests.RequestException as exc:
                self.error_string += f"Failed to query Elephant carbon intensity service for fallback: {exc}\n"
                return None

        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected Elephant response for carbon intensity: {data}")

        records = []
        for entry in data:
            time_value = entry.get('time')
            value = entry.get('carbon_intensity')

            if time_value is None or value is None:
                continue

            records.append({
                'time': self._parse_time(time_value),
                'value': float(value),
                'provider': entry.get('provider'),
            })

        df = pandas.DataFrame.from_records(records)
        if df.empty:
            return df

        df = df.sort_values(by=['time', 'provider'], ascending=True)
        df['value'] = df['value'].round().astype('int64') # We convert to int here. Could think about going to ugCO2e here.

        return df

    def _parse_metrics(self, df):

        df['detail_name'] = df['provider']
        df = df.drop(columns=['provider'])

        return df

    def _add_and_validate_sampling_rate_and_jitter(self, df):
        # Need to override
        return df
