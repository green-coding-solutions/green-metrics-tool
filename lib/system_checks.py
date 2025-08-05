# This file handles the checking of the system
# There is a list of checks that is made up of tuples structured the following way:
# - the function to call to check. This will return True or None for success and False for failure
# - What severity the False return value has. If the Status is Error we raise and exit the GMT
# - A string what is being checked
# - A string to output on WARN or INFO
# It is possible for one of the checkers or metric providers to raise an exception if something should fail specifically
# otherwise you can just return False and set the Status to ERROR for the program to abort.

import sys
import os
import subprocess
import psutil
import locale
import platform
import math

from psycopg import OperationalError as psycopg_OperationalError

from lib import utils
from lib import error_helpers
from lib.db import DB
from lib.global_config import GlobalConfig
from lib.terminal_colors import TerminalColors
from lib.configuration_check_error import ConfigurationCheckError, Status

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

GMT_Resources = {
    'free_disk': 1024 ** 3, # 1GB in bytes
    'free_memory':  1024 ** 3, # 1GB in bytes
}

######## CHECK FUNCTIONS ########
def check_db(*_, **__):
    try:
        DB().query('SELECT 1')
    except psycopg_OperationalError:
        error_helpers.log_error('DB is not available. Did you start the docker containers?')
        os._exit(1)
    return True

def check_one_energy_and_scope_machine_provider(*_, **__):
    metric_providers = utils.get_metric_providers(GlobalConfig().config).keys()
    energy_machine_providers = [provider for provider in metric_providers if ".energy" in provider and ".machine" in provider]
    return len(energy_machine_providers) <= 1

def check_tmpfs_mount(*_, **__):
    return not any(partition.mountpoint == '/tmp' and partition.fstype != 'tmpfs' for partition in psutil.disk_partitions())

def check_ntp(*_, **__):
    if platform.system() == 'Darwin': # no NTP for darwin, as this is linux cluster only functionality
        return True

    ntp_status = subprocess.check_output(['timedatectl', '-a'], encoding='UTF-8')
    if 'NTP service: inactive' not in ntp_status: # NTP must be inactive
        return False

    return True

def check_largest_sampling_rate(*_, **__):
    metric_providers = utils.get_metric_providers(GlobalConfig().config)
    if not metric_providers: # no provider provider configured passes this check
        return True

    return max(
        metric_providers.values(),
        key=lambda x: x.get('sampling_rate', 0) if x else 0
    ).get('sampling_rate', 0) <= 1000

def check_cpu_utilization(*_, **__):
    return psutil.cpu_percent(0.1) < 5.0

def check_free_disk(*_, **__):
    free_space_bytes = psutil.disk_usage(os.path.dirname(os.path.abspath(__file__))).free
    return free_space_bytes >= GMT_Resources['free_disk']

def check_free_memory(*_, **__):
    return psutil.virtual_memory().available >= GMT_Resources['free_memory']

def check_containers_running(*_, **__):
    result = subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], encoding='UTF-8')
    return not bool(result.strip())

def check_gmt_dir_dirty(*_, **__):
    return subprocess.check_output(['git', 'status', '-s'], encoding='UTF-8') == ''

def check_docker_daemon(*_, **__):
    result = subprocess.run(['docker', 'version'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=False, encoding='UTF-8')
    return result.returncode == 0

def check_utf_encoding(*_, **__):
    return locale.getpreferredencoding().lower() == sys.getdefaultencoding().lower() == 'utf-8'

# This text we compare with indicates that no swap is used
#pylint: disable=no-else-return
def check_swap_disabled(*_, **__):
    if platform.system() == 'Darwin':
        result = subprocess.check_output(['sysctl', 'vm.swapusage'], encoding='utf-8')
        return result.strip() == 'vm.swapusage: total = 0.00M  used = 0.00M  free = 0.00M  (encrypted)'
    else:
        result = subprocess.check_output(['free'], encoding='utf-8')
        for line in result.splitlines():
            # we want this output: Swap:              0           0           0
            # and condense it to Swap:000
            if line.startswith('Swap') and line.replace(' ', '') != 'Swap:000':
                return False
        return True

def check_suspend(*, run_duration):
    run_duration = math.ceil(run_duration/1e6/60)

    if platform.system() == 'Darwin': # no NTP for darwin, as this is linux cluster only functionality
        command = ['bash', '-c', f"log show --style syslog --predicate 'eventMessage contains[c] \"Entering sleep\" OR eventMessage contains[c] \"Entering Sleep\"' --last {run_duration}m"]
    else:
        command = ['journalctl', '--grep=\'suspend\'', '--output=short-iso', '--since', f"{run_duration} minutes ago", '-q']

    ps = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        encoding='UTF-8'
    )
    if ps.stderr:
        raise RuntimeError(f"Could not check for system suspend state: {ps.stderr}")

    return 'Entering' not in ps.stdout and 'suspend' not in ps.stdout

######## END CHECK FUNCTIONS ########

start_checks = (
    (check_db, Status.ERROR, 'db online', 'This text will never be triggered, please look in the function itself'),
    (check_gmt_dir_dirty, Status.WARN, 'gmt directory dirty', 'The GMT directory contains untracked or changed files - These changes will not be stored and it will be hard to understand possible changes when comparing the measurements later. We recommend only running on a clean dir.'),
    (check_one_energy_and_scope_machine_provider, Status.ERROR, 'single energy scope machine provider', 'Please only select one provider with energy and scope machine'),
    (check_tmpfs_mount, Status.INFO, 'tmpfs mount', 'We recommend to mount tmp on tmpfs'),
    (check_ntp, Status.WARN, 'ntp', 'You have NTP time syncing active. This can create noise in runs and should be deactivated.'),
    (check_cpu_utilization, Status.WARN, '< 5% CPU utilization', 'Your system seems to be busy. Utilization is above 5%. Consider terminating some processes for a more stable measurement.'),
    (check_largest_sampling_rate, Status.WARN, 'high sampling rate', 'You have chosen at least one provider with a sampling rate > 1000 ms. That is not recommended and might lead also to longer benchmarking times due to internal extra sleeps to adjust measurement frames.'),
    (check_free_disk, Status.ERROR, '1 GiB free hdd space', 'We recommend to free up some disk space (< 1GiB available)'),
    (check_free_memory, Status.ERROR, '1 GiB free memory', 'No free memory! Please kill some programs (< 1GiB available)'),
    (check_docker_daemon, Status.ERROR, 'docker daemon', 'The docker daemon could not be reached. Are you running in rootless mode or have added yourself to the docker group? See installation: [See https://docs.green-coding.io/docs/installation/]'),
    (check_containers_running, Status.WARN, 'running containers', 'You have other containers running on the system. This is usually what you want in local development, but for undisturbed measurements consider going for a measurement cluster [See https://docs.green-coding.io/docs/installation/installation-cluster/].'),
    (check_utf_encoding, Status.ERROR, 'utf file encoding', 'Your system encoding is not set to utf-8. This is needed as we need to parse console output.'),
    (check_swap_disabled, Status.WARN, 'swap disabled', 'Your system uses a swap filesystem. This can lead to very instable measurements. Please disable swap.'),
)

end_checks = (
    (check_suspend, Status.ERROR, 'system suspend', 'System has gone into suspend during measurement. This will skew all measurement data'),
)

def system_check(mode='start', system_check_threshold=3, run_duration=None):
    print(TerminalColors.HEADER, f"\nRunning System Checks - Mode: {mode}", TerminalColors.ENDC)
    warnings = []

    if mode == 'start':
        checks = start_checks
    elif mode == 'end':
        checks = end_checks
    else:
        raise RuntimeError('Unknown mode for system check:', mode)

    max_key_length = max(len(key[2]) for key in checks)

    for check in checks:
        retval = None
        try:
            retval = check[0](run_duration=run_duration)
        except ConfigurationCheckError as exp:
            raise exp
        finally:
            formatted_key = check[2].ljust(max_key_length)
            if retval or retval is None:
                output = f"{TerminalColors.OKGREEN}OK{TerminalColors.ENDC}"
            else:
                if check[1] == Status.WARN:
                    output = f"{TerminalColors.WARNING}WARN{TerminalColors.ENDC} ({check[3]})"
                    warnings.append(check[3])
                elif check[1] == Status.INFO:
                    output = f"{TerminalColors.OKCYAN}INFO{TerminalColors.ENDC} ({check[3]})"
                else:
                    output = f"{TerminalColors.FAIL}ERROR{TerminalColors.ENDC}"

            exc_type, _, _ = sys.exc_info()
            if exc_type is not None:
                output = f"{TerminalColors.FAIL}EXCEPTION{TerminalColors.ENDC}"

            print(f"Checking {formatted_key} : {output}")

            if retval is False and check[1].value >= system_check_threshold:
                # Error needs to raise
                raise ConfigurationCheckError(check[3], check[1])

    return warnings
