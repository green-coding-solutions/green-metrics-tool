import os
import subprocess
import plistlib
from datetime import timezone
import time
import xml
import pandas

from lib.db import DB
from metric_providers.base import MetricProviderConfigurationError, BaseMetricProvider

class PowermetricsProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name='powermetrics',
            metrics={'time': int, 'value': int},
            resolution=resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable='/usr/bin/powermetrics',
            sudo=True,
        )

        # We can't use --show-all here as this sometimes triggers output on stderr
        self._extra_switches = [
            '--show-process-io',
            '--show-process-gpu',
            '--show-process-netstats',
            '--show-process-energy',
            '--show-process-coalition',
            '-f',
            'plist',
            '-o',
            self._filename]

    def check_system(self):
        if self.is_powermetrics_running():
            raise MetricProviderConfigurationError('Another instance of powermetrics is already running on the system!\nPlease close it before running the Green Metrics Tool.')

    def is_powermetrics_running(self):
        ps = subprocess.run(['pgrep', '-qx', 'powermetrics'], check=False)
        if ps.returncode == 1:
            return False
        return True


    def stop_profiling(self):
        try:
            # We try calling the parent method but if this doesn't work we use the more hardcore approach
            super().stop_profiling()
        except PermissionError:
            #This isn't the nicest way of doing this but there isn't really any other way that is nicer
            subprocess.check_output('sudo /usr/bin/killall powermetrics', shell=True)
            print('Killed powermetrics process with killall!')

        # As killall returns right after sending the SIGKILL we need to wait and make sure that the process
        # had time to flush everything to disk
        count = 0
        while self.is_powermetrics_running():
            print(f"Waiting for powermetrics to shut down (try {count}/60). Please do not abort ...")
            time.sleep(1)
            count += 1
            if count >= 60:
                subprocess.check_output('sudo /usr/bin/killall -9 powermetrics', shell=True)
                raise RuntimeError('powermetrics had to be killed with kill -9. Values can not be trusted!')

        # We need to give the OS a second to flush
        time.sleep(1)

        self._ps = None

    def read_metrics(self, run_id, containers=None):

        with open(self._filename, 'rb') as metrics_file:
            datas = metrics_file.read()

        datas = datas.split(b'\x00')

        # We allow the usage of `df` and `dfs` here as it makes the code a lot more readable and is convention
        # pylint: disable=invalid-name
        dfs = []
        cum_time = None

        for count, data in enumerate(datas, start=1):
            try:
                data = plistlib.loads(data)
            except xml.parsers.expat.ExpatError as e:
                print('There was an error parsing the powermetrics data!')
                print(f"Iteration count: {count}")
                print(f"Number of items in datas: {len(datas)}")
                print(data)
                raise e

            if cum_time is None:
                # Convert seconds to nano seconds
                cum_time = int(data['timestamp'].replace(tzinfo=timezone.utc).timestamp() * 1e9)

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
                            'cpu_time_powermetrics_vm',
                            'docker_vm',
                            'ns'])
                dfs.append([cum_time_ms,
                            docker_task['diskio_bytesread'],
                            'disk_io_bytesread_powermetrics_vm',
                            'docker_vm',
                            'Bytes'])
                dfs.append([cum_time_ms,
                            docker_task['diskio_byteswritten'],
                           'disk_io_byteswritten_powermetrics_vm',
                           'docker_vm',
                           'Bytes'])
                dfs.append([cum_time_ms,
                            int(docker_task['energy_impact']),
                           'energy_impact_powermetrics_vm',
                           'docker_vm',
                           # We need to introduce a new unit here as the energy impact on Mac isn't well understood
                           # https://tinyurl.com/2p9c56pz
                           '*'])

            if 'cpu_power' in data['processor']:
                dfs.append([cum_time_ms,
                            int(float(data['processor']['cpu_power']) * conversion_factor),
                           'cores_energy_powermetrics_component',
                           '[COMPONENT]',
                           'mJ'])

            if 'package_joules' in data['processor']:
                dfs.append([cum_time_ms,
                            int(float(data['processor']['package_joules']) * 1000),
                           'cpu_energy_powermetrics_component',
                           '[COMPONENT]',
                           'mJ'])

            if 'gpu_power' in data['processor']:
                dfs.append([cum_time_ms,
                            int(float(data['processor']['gpu_power']) * conversion_factor),
                            'gpu_energy_powermetrics_component',
                            '[COMPONENT]',
                            'mJ'])

            #if 'combined_power' in data['processor']:
            #    dfs.append([cum_time_ms,
            #                int(float(data['processor']['combined_power']) * conversion_factor),
            #                'system_combined_power',
            #                '[COMPONENT]',
            #                'mJ'])

            if 'ane_power' in data['processor']:
                dfs.append([cum_time_ms,
                            int(float(data['processor']['ane_power']) * conversion_factor),
                            'ane_energy_powermetrics_component',
                            '[COMPONENT]',
                            'mJ'])

        df = pandas.DataFrame.from_records(dfs, columns=['time', 'value', 'metric', 'detail_name', 'unit'])

        df['run_id'] = run_id

        # Set the invalid run string to indicate, that it was mac and we can't rely on the data
        invalid_message = 'Measurements are not reliable as they are done on a Mac. See our blog for details.'
        DB().query('UPDATE runs SET invalid_run=%s WHERE id = %s', params=(invalid_message, run_id))

        return df

    # powermetrics sometimes generates output to stderr. This isn't really a problem for our measurements
    def get_stderr(self):
        stderr = super().get_stderr()

        if stderr is not None and str(stderr).find('proc_pid') != -1:
            return None

        return stderr
