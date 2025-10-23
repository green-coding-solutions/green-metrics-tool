import os
from pathlib import Path
import platform
import subprocess
from io import StringIO
import pandas
from typing import final

from lib.system_checks import ConfigurationCheckError
from lib import process_helpers

class MetricProviderConfigurationError(ConfigurationCheckError):
    pass

class BaseMetricProvider:

    def __init__(self, *,
        metric_name,
        metrics,
        sampling_rate,
        unit,
        current_dir,
        metric_provider_executable='metric-provider-binary',
        sudo=False,
        disable_buffer=True,
        skip_check=False,
    ):
        self._metric_name = metric_name
        self._metrics = metrics
        self._sampling_rate = sampling_rate
        self._unit = unit
        self._current_dir = current_dir
        self._metric_provider_executable = metric_provider_executable
        self._sudo = sudo
        self._has_started = False
        self._disable_buffer = disable_buffer
        self._skip_check = skip_check

        self._tmp_folder = '/tmp/green-metrics-tool'
        self._ps = None

        Path(self._tmp_folder).mkdir(exist_ok=True)

        self._filename = f"{self._tmp_folder}/{self._metric_name}.log"

        if not self._skip_check:
            self.check_system()

    # this is the default function that can be overridden in the children
    # by default we expect the executable to have a -c switch to test functionality
    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        if check_command is not None:
            if check_command == "default":
                call_string = self._metric_provider_executable
                if self._metric_provider_executable[0] != '/':
                    call_string = f"{self._current_dir}/{call_string}"
                check_command = [f"{call_string}", '-c']

            ps = subprocess.run(check_command, capture_output=True, encoding='UTF-8', check=False)
            if ps.returncode != 0:
                if check_error_message is None:
                    check_error_message = ps.stderr
                raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nError: {check_error_message}\nAre you running in a VM / cloud / shared hosting?\nIf so please disable the {self._metric_name} provider in the config.yml")

        ## Check if another instance of the same metric provider is already running
        if check_parallel_provider:
            cmd = ['pgrep', '-f', self._metric_provider_executable]
            result = subprocess.run(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                check=False, encoding='UTF-8', errors='replace')
            if result.returncode == 1:
                pass
            elif result.returncode == 0:
                raise MetricProviderConfigurationError(f"Another instance of the {self._metric_name} metrics provider is already running on the system!\nPlease close it before running the Green Metrics Tool.")
            else:
                raise subprocess.CalledProcessError(result.stderr, cmd)

        return True

    # implemented as getter function and not direct access, so it can be overloaded
    # some child classes might not actually have _ps attribute set
    #
    # This function has to go through quite some hoops to read the stderr
    # The preferred way to communicate with processes is through communicate()
    # However this function ALWAYS waits for the process to terminate and it does not allow reading from processes
    # in chunks while they are running. Thus we we cannot set encoding='UTF-8' in Popen and must decode here.
    def get_stderr(self):
        stderr_read = ''
        if self._ps.stderr is not None:
            stderr_read = self._ps.stderr.read()
            if isinstance(stderr_read, bytes):
                stderr_read = stderr_read.decode('utf-8', errors='replace')
        return stderr_read

    def has_started(self):
        return self._has_started

    def _check_monotonic(self, df):
        if not df['time'].is_monotonic_increasing: # this is not strict. Means we still can have duplicates which is checked later
            raise ValueError(f"Time from metric provider {self._metric_name} is not monotonic increasing")

    def _check_resolution_underflow(self, df):
        if self._unit in ['mJ', 'uJ', 'Hz', 'us']:
            if (df['value'] <= 1).any():
                raise ValueError(f"Data from metric provider {self._metric_name} is running into a resolution underflow. Values are <= 1 {self._unit}")

    def _read_metrics(self):  # can be overriden in child
        with open(self._filename, 'r', encoding='utf-8') as file:
            csv_data = file.read()

        # remove the last line from the string, as it may be broken due to the output buffering of the metrics reporter
        csv_data = csv_data[:csv_data.rfind('\n')]

        # pylint: disable=invalid-name
        df = pandas.read_csv(StringIO(csv_data),
                             sep=' ',
                             names=self._metrics.keys(),
                             dtype=self._metrics
                             )

        if df.isna().any().any():
            raise ValueError(f"Dataframe for {self._metric_name} contained NA values.")

        return df

    def _check_empty(self, df):
        if df.empty:
            raise RuntimeError(f"Metrics provider {self._metric_name} seems to have not produced any measurements. Metrics log file was empty. Either consider having a higher sample rate or turn off provider.")


    def _parse_metrics(self, df): # can be overriden in child
        df['detail_name'] = f"[{self._metric_name.split('_')[-1].upper()}]" # default, can be overridden in child
        return df

    def _add_and_validate_sampling_rate_and_jitter(self, df):
        # DF can have many columns still. Since all of them might have induced a separate timing row
        # we group by everything apart from time and value itself
        # for most metric providers only detail_name and container_id should be present and differ though
        excluded_columns = ['time', 'value']
        grouping_columms = [col for col in df.columns if col not in excluded_columns]
        df['sampling_rate'] = df.groupby(grouping_columms)['time'].diff()
        df['sampling_rate_95p'] = df.groupby(grouping_columms)['sampling_rate'].transform(lambda x: x.quantile(0.95))
        df = df.drop('sampling_rate', axis=1)

        if (sampling_rate_95p := df['sampling_rate_95p'].max()) >= self._sampling_rate*1000*1.2:
            raise RuntimeError(f"Effective sampling rate (95p) was absurdly high: {sampling_rate_95p} compared to configured rate of {self._sampling_rate*1000}", df)

        if (sampling_rate_95p := df['sampling_rate_95p'].min()) <= self._sampling_rate*1000*0.8:
            raise RuntimeError(f"Effective sampling rate (95p) was absurdly low: {sampling_rate_95p} compared to configured rate of {self._sampling_rate*1000}", df)

        return df

    def _add_auxiliary_fields(self, df): # can be overriden in child
        if 'unit' not in df.columns:
            df['unit'] = self._unit
        if 'metric' not in df.columns:
            df['metric'] = self._metric_name
        return df

    def _check_unique(self, df):
        if not (df.groupby(['metric', 'detail_name'])['time'].transform('nunique') == df.groupby(['metric', 'detail_name'])['time'].transform('size')).all():
            raise ValueError(f"Metric provider {self._metric_name} did contain non unique timestamps for measurement values. This is not allowed and indicates an error with the clock.")

    @final
    def read_metrics(self): # should not be overriden

        df = self._read_metrics() # is not always returning a data frame, but can in rare cases also return a list if no actual numeric measurements are captured

        self._check_empty(df) # initial check bc it is cheap

        self._check_monotonic(df) # check must be made before data frame is potentially sorted in _parse_metrics
        self._check_resolution_underflow(df)

        df = self._parse_metrics(df) # can return DataFrame or [] when metrics are expanded

        def process_df(df):
            df = self._add_auxiliary_fields(df)
            df = self._add_and_validate_sampling_rate_and_jitter(df)
            self._check_unique(df)
            self._check_empty(df) # final check bc _parse_metrics could have altered the dataframe
            return df

        return process_df(df) if not isinstance(df, list) else [process_df(dfi) for dfi in df]

    def _add_extra_switches(self, call_string): # will be adapted in child if needed
        return call_string

    def start_profiling(self):

        if self._sampling_rate is None:
            call_string = self._metric_provider_executable
        else:
            call_string = f"{self._metric_provider_executable} -i {self._sampling_rate}"


        if self._metric_provider_executable[0] != '/':
            call_string = f"{self._current_dir}/{call_string}"

        if self._sudo:
            call_string = f"sudo {call_string} "

        call_string = self._add_extra_switches(call_string)

        call_string += f" > {self._filename}"

        if platform.system() == "Linux":
            call_string = f"taskset -c 0 {call_string}"

        if self._disable_buffer:
            call_string = f"stdbuf -o0 {call_string}"

        print(call_string)

        #pylint: disable=consider-using-with,subprocess-popen-preexec-fn
        self._ps = subprocess.Popen(
            [call_string],
            shell=True,
            preexec_fn=os.setsid,
            stderr=subprocess.PIPE,
            #encoding='UTF-8' # we cannot set this option here as reading later will then flake with "can't concat NoneType to bytes"
                              # see get_stderr() for additional details
            # since we are launching the command with shell=True we cannot use ps.terminate() / ps.kill().
            # This would just kill the executing shell, but not it's child and make the process an orphan.
            # therefore we use os.setsid here and later call os.getpgid(pid) to get process group that the shell
            # and the process are running in. These we then can send the signal to and kill them
        )

        # set_block False enables non-blocking reads on stderr.read(). Otherwise it would wait forever on empty
        os.set_blocking(self._ps.stderr.fileno(), False)
        self._has_started = True

    def stop_profiling(self):
        if self._ps is None:
            return

        process_helpers.kill_pg(self._ps, self._metric_provider_executable)
        self._ps = None
        self._has_started = False
