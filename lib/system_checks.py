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
def check_db():
    try:
        DB().query('SELECT 1')
    except psycopg_OperationalError:
        error_helpers.log_error('DB is not available. Did you start the docker containers?')
        os._exit(1)
    return True

def check_one_energy_and_scope_machine_provider():
    metric_providers = utils.get_metric_providers(GlobalConfig().config).keys()
    energy_machine_providers = [provider for provider in metric_providers if ".energy" in provider and ".machine" in provider]
    return len(energy_machine_providers) <= 1

def check_tmpfs_mount():
    return not any(partition.mountpoint == '/tmp' and partition.fstype != 'tmpfs' for partition in psutil.disk_partitions())

def check_cpu_utilization():
    return psutil.cpu_percent(0.1) < 5.0

def check_free_disk():
    free_space_bytes = psutil.disk_usage(os.path.dirname(os.path.abspath(__file__))).free
    return free_space_bytes >= GMT_Resources['free_disk']

def check_free_memory():
    return psutil.virtual_memory().available >= GMT_Resources['free_memory']

def check_energy_filtering():
    if platform.system() != 'Linux':
        print(TerminalColors.WARNING, '>>>> RAPL could not be checked as not running on Linux platform <<<<', TerminalColors.ENDC)
        return True

    result = subprocess.run(['sudo', 'python3', '-m', 'lib.hardware_info_root', '--read-rapl-energy-filtering'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=os.path.abspath(os.path.join(CURRENT_DIR, '..')),
                            check=True, encoding='UTF-8')
    return "1" != result.stdout.strip()

def check_containers_running():
    result = subprocess.run(['docker', 'ps', '--format', '{{.Names}}'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=True, encoding='UTF-8')
    return not bool(result.stdout.strip())

def check_docker_daemon():
    result = subprocess.run(['docker', 'version'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=False, encoding='UTF-8')
    return result.returncode == 0

def check_utf_encoding():
    return locale.getpreferredencoding().lower() == sys.getdefaultencoding().lower() == 'utf-8'

######## END CHECK FUNCTIONS ########

start_checks = [
    (check_db, Status.ERROR, 'db online', 'This text will never be triggered, please look in the function itself'),
    (check_one_energy_and_scope_machine_provider, Status.ERROR, 'single energy scope machine provider', 'Please only select one provider with energy and scope machine'),
    (check_tmpfs_mount, Status.INFO, 'tmpfs mount', 'We recommend to mount tmp on tmpfs'),
    (check_cpu_utilization, Status.WARN, '< 5% CPU utilization', 'Your system seems to be busy. Utilization is above 5%. Consider terminating some processes for a more stable measurement.'),
    (check_free_disk, Status.ERROR, '1GB free hdd space', 'We recommend to free up some disk space'),
    (check_free_memory, Status.ERROR, 'free memory', 'No free memory! Please kill some programs'),
    (check_docker_daemon, Status.ERROR, 'docker daemon', 'The docker daemon could not be reached. Are you running in rootless mode or have added yourself to the docker group? See installation: [See https://docs.green-coding.io/docs/installation/]'),
    (check_containers_running, Status.WARN, 'running containers', 'You have other containers running on the system. This is usually what you want in local development, but for undisturbed measurements consider going for a measurement cluster [See https://docs.green-coding.io/docs/installation/installation-cluster/].'),
    (check_utf_encoding, Status.ERROR, 'utf file encoding', 'Your system encoding is not set to utf-8. This is needed as we need to parse console output.'),
    (check_energy_filtering, Status.ERROR, 'rapl energy filtering', 'RAPL Energy filtering is active!'),
]

def check_start():
    print(TerminalColors.HEADER, '\nRunning System Checks', TerminalColors.ENDC)
    max_key_length = max(len(key[2]) for key in start_checks)

    for check in start_checks:
        retval = None
        try:
            retval = check[0]()
        except ConfigurationCheckError as exp:
            raise exp
        finally:
            formatted_key = check[2].ljust(max_key_length)
            if retval or retval is None:
                output = f"{TerminalColors.OKGREEN}OK{TerminalColors.ENDC}"
            else:
                if check[1] == Status.WARN:
                    output = f"{TerminalColors.WARNING}WARN{TerminalColors.ENDC} ({check[3]})"
                elif check[1] == Status.INFO:
                    output = f"{TerminalColors.OKCYAN}INFO{TerminalColors.ENDC} ({check[3]})"
                else:
                    output = f"{TerminalColors.FAIL}ERROR{TerminalColors.ENDC}"

            exc_type, _, _ = sys.exc_info()
            if exc_type is not None:
                output = f"{TerminalColors.FAIL}EXCEPTION{TerminalColors.ENDC}"

            print(f"Checking {formatted_key} : {output}")

            if retval is False and check[1].value >= GlobalConfig().config['measurement']['system_check_threshold']:
                # Error needs to raise
                raise ConfigurationCheckError(check[3], check[1])
