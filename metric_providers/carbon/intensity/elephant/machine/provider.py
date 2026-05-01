import os
from datetime import datetime, timezone

import pandas
import requests

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError
from metric_providers.carbon.intensity.helpers import expand_to_sampling_rate

class CarbonIntensityElephantMachineProvider(BaseMetricProvider):
    def __init__(self, *, region, elephant, folder, sampling_rate=-1, simulation_uuid=None, provider=None, skip_check=False):

        self.region = region
        self.provider_filter = provider
        self.elephant = elephant or {}
        self.simulation_uuid = simulation_uuid
        self._start_time = None
        self._end_time = None
        self._elephant_base_url = None
        self._error_string = ""
        self._folder = folder

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
            sampling_rate=sampling_rate,
            unit='gCO2e/kWh',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
        )

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        super().check_system(check_command=None, check_parallel_provider=False)
        response = None
        try:
            response = requests.get(f"{self._elephant_base_url}/health", timeout=10)
            if response.json().get('status', '').lower() != 'healthy':
                raise MetricProviderConfigurationError(f"Elephant service health check failed. Expected 'healthy' but got: {response.text}")
        except requests.RequestException as exc:
            raise MetricProviderConfigurationError(f"Elephant base URL {self._elephant_base_url} could not be reached: {exc}") from exc
        finally:
            if response is not None:
                response.close()

    def get_stderr(self):
        return self._error_string

    def start_profiling(self, _=None):
        self._start_time = datetime.now(timezone.utc)
        self._has_started = True

    def stop_profiling(self):
        self._end_time = datetime.now(timezone.utc)
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
        if self._start_time is None or self._end_time is None:
            raise RuntimeError(
                f"{self._metric_name} provider did not record start/end times. Did start_profiling and stop_profiling run?")

        params = {
            'region': self.region,
            'startTime': self._format_time(self._start_time),
            'endTime': self._format_time(self._end_time),
            'update': 'true',
        }

        if self.provider_filter:
            params['provider'] = f"{self.provider_filter.lower()}_{self.region.lower()}"

        if self.simulation_uuid:
            params['simulationId'] = str(self.simulation_uuid)

        url = f"{self._elephant_base_url}/carbon-intensity/history"
        response = None
        try:
            response = requests.get(url, params=params, timeout=30)
        except requests.RequestException as exc:
            self._error_string += f"Failed to query Elephant carbon intensity service: {exc}\n"
            return pandas.DataFrame(columns=['time', 'value', 'provider'])

        finally:
            if response is not None:
                response.close()

        if response.status_code != 200:
            self._error_string += f"Elephant carbon intensity request failed with status {response.status_code}: {response.text}\n"
            return pandas.DataFrame(columns=['time', 'value', 'provider'])

        data = response.json()

        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected Elephant response for carbon intensity: {data}")

        if len(data) == 0:
            # As the providers take quite some time to provide data (5 min to 1 hour) it can happen that short running
            # jobs don't have any data. So we just get the most current data point as a fallback.
            if self.provider_filter:
                fallback_url = f"{self._elephant_base_url}/carbon-intensity/current"
            else:
                fallback_url = f"{self._elephant_base_url}/carbon-intensity/current/primary"

            fallback_response = None
            try:
                fallback_params = {'region': self.region}
                if self.simulation_uuid:
                    fallback_params['simulationId'] = str(self.simulation_uuid)

                fallback_response = requests.get(fallback_url, params=fallback_params, timeout=30)

                if fallback_response.status_code != 200:
                    self._error_string += f"Elephant carbon intensity fallback request failed with status {fallback_response.status_code}: {fallback_response.text}\n"
                    return pandas.DataFrame(columns=['time', 'value', 'provider'])

                data = fallback_response.json()

                if isinstance(data, dict) and self.simulation_uuid:
                    data = [{
                        'time': self._format_time(self._end_time),
                        'carbon_intensity': data.get('carbon_intensity'),
                        'provider': data.get('simulationId', str(self.simulation_uuid)),
                    }]

                if not isinstance(data, list):
                    raise RuntimeError(f"Unexpected Elephant response for carbon intensity: {data}")

                if self.provider_filter:
                    data = [d for d in data if d.get('provider') == f"{self.provider_filter.lower()}_{self.region.lower()}"]

            except requests.RequestException as exc:
                self._error_string += f"Failed to query Elephant carbon intensity service for fallback: {exc}\n"
                return pandas.DataFrame(columns=['time', 'value', 'provider'])

            finally:
                if fallback_response is not None:
                    fallback_response.close()

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
        df = expand_to_sampling_rate(self, df)

        return df

    def _parse_metrics(self, df):

        df['detail_name'] = df['provider']
        df = df.drop(columns=['provider'])

        return df

    def _add_and_validate_sampling_rate_and_jitter(self, df):
        # Need to override
        return df
