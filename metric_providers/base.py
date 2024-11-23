import os
from pathlib import Path
import platform
import subprocess
from io import StringIO
import pandas

from lib.system_checks import ConfigurationCheckError
from lib import process_helpers

class MetricProviderConfigurationError(ConfigurationCheckError):
    pass

class BaseMetricProvider:

    def __init__(
        self,
        metric_name,
        metrics,
        resolution,
        unit,
        current_dir,
        metric_provider_executable='metric-provider-binary',
        sudo=False,
        disable_buffer=True,
        skip_check=False,
    ):
        self._metric_name = metric_name
        self._metrics = metrics
        self._resolution = resolution
        self._unit = unit
        self._current_dir = current_dir
        self._metric_provider_executable = metric_provider_executable
        self._sudo = sudo
        self._has_started = False
        self._disable_buffer = disable_buffer
        self._skip_check = skip_check

        self._tmp_folder = '/tmp/green-metrics-tool'
        self._ps = None
        self._extra_switches = []

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
                                check=False, encoding='UTF-8')
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
                stderr_read = stderr_read.decode('utf-8')
        return stderr_read

    def has_started(self):
        return self._has_started

    def check_monotonic(self, df):
        if not df['time'].is_monotonic_increasing:
            raise ValueError(f"Data from metric provider {self._metric_name} is not monotonic increasing")

    def check_resolution_underflow(self, df):
        if self._unit in ['mJ', 'uJ', 'Hz', 'us']:
            if (df['value'] <= 1).any():
                raise ValueError(f"Data from metric provider {self._metric_name} is running into a resolution underflow. Values are <= 1 {self._unit}")



    def read_metrics(self, run_id, containers=None): #pylint: disable=unused-argument
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

        df['detail_name'] = f"[{self._metric_name.split('_')[-1]}]" # default, can be overridden in child
        df['unit'] = self._unit
        df['metric'] = self._metric_name
        df['run_id'] = run_id

        self.check_monotonic(df)
        self.check_resolution_underflow(df)

        return df

    def start_profiling(self, containers=None):

        if self._resolution is None:
            call_string = self._metric_provider_executable
        else:
            call_string = f"{self._metric_provider_executable} -i {self._resolution}"


        if self._metric_provider_executable[0] != '/':
            call_string = f"{self._current_dir}/{call_string}"

        if self._sudo:
            call_string = f"sudo {call_string} "

        if hasattr(self, '_extra_switches'):
            call_string += ' '  # space at start
            call_string += ' '.join(self._extra_switches)

        # This needs refactoring see https://github.com/green-coding-solutions/green-metrics-tool/issues/45
        if (self._metrics.get('container_id') is not None) and (containers is not None):
            call_string += ' -s '
            call_string += ','.join(containers.keys())

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
