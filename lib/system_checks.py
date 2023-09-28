# This file handles the checking of the system
# There is a list of checks that is made up of tuples structured the following way:
# - the function to call to check. This will return True or None for success and False for failure
# - What severity the False return value has. If the Status is Error we raise and exit the GMT
# - A string what is being checked
# - A string to output on WARN or INFO
# It is possible for one of the checkers or metric providers to raise an exception if something should fail specifically
# otherwise you can just return False and set the Status to ERROR for the program to abort.

#pylint: disable=inconsistent-return-statements


import sys
import os
from enum import Enum
import subprocess
import psutil

from lib import utils
from lib.global_config import GlobalConfig
from lib.terminal_colors import TerminalColors

Status = Enum('Status', ['ERROR', 'INFO', 'WARN'])

class ConfigurationCheckError(Exception):
    pass

######## CHECK FUNCTIONS ########
def check_metric_providers(runner):
    for metric_provider in runner._Runner__metric_providers:
        if hasattr(metric_provider, 'check_system'):
            if metric_provider.check_system() is False:
                return False

def check_one_psu_provider(_):
    metric_providers = list(utils.get_metric_providers(GlobalConfig().config).keys())
    if sum(True for provider in metric_providers if ".energy" in provider and ".machine" in provider) > 1:
        return False

def check_tmpfs_mount(_):
    for partition in psutil.disk_partitions():
        if partition.mountpoint == '/tmp' and partition.fstype != 'tmpfs':
            return False

def check_free_disk(percent):
    # We are assuming that the GMT is installed on the system partition!
    usage = psutil.disk_usage(os.path.abspath(__file__))
    if usage.percent >= percent:
        return False

def check_free_disk_80(_):
    return check_free_disk(80)

def check_free_disk_90(_):
    return check_free_disk(90)

def check_free_disk_95(_):
    return check_free_disk(95)

def check_free_memory(_):
    if psutil.virtual_memory().percent >= 70:
        return False

def check_containers_running(_):
    result = subprocess.run(['docker', 'ps' ,'--format', '{{.Names}}'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=True, encoding='UTF-8')
    if result.stdout:
        return False

def check_docker_daemon(_):
    result = subprocess.run(['docker', 'version'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=False, encoding='UTF-8')
    if result.returncode == 0:
        return True
    return False


######## END CHECK FUNCTIONS ########

checks = [
    (check_metric_providers, Status.ERROR, 'metric providers', 'Metric provider failed'),
    (check_one_psu_provider, Status.ERROR, 'single PSU provider', 'Please only select one PSU provider'),
    (check_tmpfs_mount, Status.INFO, 'tmpfs mount', 'We recommend to mount tmp on tmpfs'),
    (check_free_disk_80, Status.INFO, '80% free disk space', 'We recommend to free up some disk space'),
    (check_free_disk_90, Status.WARN, '90% free disk space', 'We recommend to free up some disk space!!!!!!!'),
    (check_free_disk_95, Status.ERROR, '95% free disk space', 'No free disk space left. Please clean up some files'),
    (check_free_memory, Status.ERROR, '80% free memory', 'No free memory! Please kill some programs'),
    (check_docker_daemon, Status.ERROR, 'docker daemon', 'The docker daemon could not be reached. Are you running in rootless mode or have added yourself to the docker group? See installation: [See https://docs.green-coding.berlin/docs/installation/]'),
    (check_containers_running, Status.WARN, 'Running containers', 'You have other containers running on the system. This is usually what you want in local development, but for undisturbed measurements consider going for a measurement cluster [See https://docs.green-coding.berlin/docs/installation/installation-cluster/].'),

]


def check_all(runner):
    print(TerminalColors.HEADER, '\nRunning System Checks', TerminalColors.ENDC)
    max_key_length = max(len(key[2]) for key in checks)

    for check in checks:
        retval = None
        try:
            retval = check[0](runner)
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

            if retval is False and check[1] == Status.ERROR:
                # Error needs to raise
                raise ConfigurationCheckError(check[3])
