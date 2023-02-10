import os
import subprocess
import plistlib
import datetime
import pandas
import pytz

#pylint: disable=import-error
from db import DB
from metric_providers.base import BaseMetricProvider


class PowermetricsProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="powermetrics",
            metrics={'time': int, 'value': int},
            resolution=resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )

        # We can't use --show-all here as this sometimes triggers output on stderr
        self._extra_switches = [
            "--show-process-io",
            "--show-process-gpu",
            "--show-process-netstats",
            "--show-process-energy",
            "--show-process-coalition",
            '-f',
            'plist',
            '-o',
            self._filename]

    def stop_profiling(self):
        try:
            # We try calling the parent method but if this doesn't work we use the more hardcore approach
            super().stop_profiling()
        except PermissionError:
            # This isn't the nicest way of doing this but there isn't really any other way that is nicer
            subprocess.check_output('sudo /usr/bin/killall powermetrics', shell=True)

        self._ps = None

    # pylint: disable=too-many-locals
    def read_metrics(self, project_id, containers=None):

        with open(self._filename, 'rb') as metrics_file:
            datas = metrics_file.read()

        datas = datas.split(b'\x00')

        # We allow the usage of `df` and `dfs` here as it makes the code a lot more readable and is convention
        # pylint: disable=invalid-name
        dfs = []
        cum_time = None

        for data in datas:
            data = plistlib.loads(data)

            if cum_time is None:
                # Get the system's local timezone
                local_tz = pytz.timezone(datetime.datetime.now().astimezone().tzname())

                # Set the timezone on the timestamp to UTC
                utc_time = pytz.timezone('UTC').localize(data['timestamp'])

                # Convert the datetime object to the system's local timezone
                local_dt = utc_time.astimezone(local_tz)

                # Convert seconds to nano seconds
                cum_time = int(local_dt.timestamp() * 1e9)

            cum_time = cum_time + data['elapsed_ns']

            # we want microjoule. Therefore / 10**9 to get seconds and the values are already in mW
            conversion_factor = data['elapsed_ns'] / 1_000_000_000
            cum_time_ms = int(cum_time / 1_000)

            # coalitions gives us a list so we need to find the named entry
            docker_task = None
            for i in data['coalitions']:
                if i['name'] == 'com.docker.docker':
                    docker_task = i
                    break

            if docker_task is not None:
                dfs.append([cum_time_ms,
                            docker_task['cputime_ns'],
                            'docker_cpu_time', 'docker',
                            'ns'])
                dfs.append([cum_time_ms,
                            docker_task['diskio_bytesread'],
                            'docker_bytesread',
                            'docker',
                            'bytes'])
                dfs.append([cum_time_ms,
                            docker_task['diskio_byteswritten'],
                           'docker_byteswritten',
                           'docker',
                           'bytes'])
                dfs.append([cum_time_ms,
                            int(docker_task['energy_impact']),
                           'docker_energy_impact',
                           'energy_impact',
                           # We need to introduce a new unit here as the energy impact on Mac isn't well understood
                           # https://tinyurl.com/2p9c56pz
                           '*'])

            if 'cpu_power' in data['processor']:
                dfs.append([cum_time_ms,
                            int(float(data['processor']['cpu_power']) * conversion_factor),
                           'system_cpu_power',
                           '[SYSTEM]',
                           'mJ'])

            if 'package_joules' in data['processor']:
                dfs.append([cum_time_ms,
                            int(float(data['processor']['package_joules']) * 1000),
                           'package_joules',
                           '[SYSTEM]',
                           'mJ'])

            if 'gpu_power' in data['processor']:
                dfs.append([cum_time_ms,
                            int(float(data['processor']['gpu_power']) * conversion_factor),
                            'system_gpu_power',
                            '[SYSTEM]',
                            'mJ'])

            if 'combined_power' in data['processor']:
                dfs.append([cum_time_ms,
                            int(float(data['processor']['combined_power']) * conversion_factor),
                            'system_combined_power',
                            '[SYSTEM]',
                            'mJ'])

            if 'ane_power' in data['processor']:
                dfs.append([cum_time_ms,
                            int(float(data['processor']['ane_power']) * conversion_factor),
                            'system_ane_power',
                            '[SYSTEM]',
                            'mJ'])

        df = pandas.DataFrame.from_records(dfs, columns=['time', 'value', 'metric', 'detail_name', 'unit'])

        df['project_id'] = project_id

        # Set the invalid project string to indicate, that it was mac and we can't rely on the data
        invalid_message = 'Measurements are not reliable as they are done on a Mac. See our blog for details.'
        DB().query('UPDATE projects SET invalid_project=%s WHERE id = %s', params=(invalid_message, project_id))

        return df

    # powermetrics sometimes generates output to stderr. This isn't really a problem for our measurements
    def get_stderr(self):
        stderr = super().get_stderr()

        if stderr is not None and str(stderr).find('proc_pidinfo') != -1:
            return None

        return stderr
