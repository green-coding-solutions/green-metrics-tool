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
import re
import subprocess
import functools
import psutil
import locale
import platform
import math
import json
from pathlib import Path

from psycopg import OperationalError as psycopg_OperationalError

from lib import utils
from lib import error_helpers
from lib import host_platform
from lib import resource_limits
from lib.db import DB
from lib.global_config import GlobalConfig
from lib.terminal_colors import TerminalColors
from lib.configuration_check_error import ConfigurationCheckError, Status, TemperatureException
from lib.temperature import get_temperature

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

GMT_RESOURCES = {
    'min_cpus': 2,
    'free_disk': 1024 ** 3, # 1 GB in Bytes
    'free_memory': 2 * 1024**3, # 2 GB in Bytes
}

# Sentinel returned by a check when it is skipped because the relevant machine.* option
# is not set in config.yml at all. Distinct from None, which checks return when they are
# skipped for environment reasons (unsupported platform, tool unavailable, etc).
NOT_CONFIGURED = 'not_configured'

######## CHECK FUNCTIONS ########
def check_db(*_, **__):
    try:
        DB().query('SELECT 1')
    except psycopg_OperationalError:
        error_helpers.log_error('DB is not available. Did you start the docker containers?')
        os._exit(1)
    return True

def check_docker_host_env(*_, **__):
    if host_platform.is_windows():
        return True
    return 'rootless' not in subprocess.check_output(['docker', 'info'], encoding='UTF-8', errors='replace') or os.getenv('DOCKER_HOST', '') != ''

def check_one_energy_and_scope_machine_provider(*_, **__):
    metric_providers = utils.get_metric_providers(GlobalConfig().config).keys()
    energy_machine_providers = [provider for provider in metric_providers if "_energy_" in provider and "_machine" in provider]
    return len(energy_machine_providers) <= 1

def check_tmpfs_mount(*_, **__):
    if host_platform.is_windows():
        return True
    return not any(partition.mountpoint == '/tmp' and partition.fstype != 'tmpfs' for partition in psutil.disk_partitions())

def check_ntp(*_, **__):
    if platform.system() in ('Darwin', 'Windows'): # no NTP for darwin/windows, as this is linux cluster only functionality
        return True

    ntp_status = subprocess.check_output(['timedatectl', '-a'], encoding='UTF-8', errors='replace')
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
    return free_space_bytes >= GMT_RESOURCES['free_disk']

def check_available_cpus(*_, **__): # GMT min system requirement
    return os.cpu_count() >= GMT_RESOURCES['min_cpus']

def check_docker_cpu_availability(*_, **__):
    if platform.system() in ('Darwin', 'Windows'):
        return True # no checks as Docker runs in a VM here with custom CPU configuration
    return os.cpu_count() == resource_limits.get_docker_available_cpus()

def check_assignable_cpus(*_, **__):
    return resource_limits.get_assignable_cpus() > 0

def check_free_memory(*_, **__):
    # Here we explicitely check on the host and not how much docker has assigned, as memory is not blocked exclusively by Docker
    return psutil.virtual_memory().available >= GMT_RESOURCES['free_memory']

def check_assignable_memory(*_, **__):
    return resource_limits.get_assignable_memory() >= 0

def check_assignable_memory_oom(*_, **__):
    return resource_limits.get_assignable_memory() <= psutil.virtual_memory().available

def check_containers_running(*_, **__):
    result = subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], encoding='UTF-8', errors='replace')
    return not bool(result.strip())

def check_gmt_dir_dirty(*_, **__):
    return subprocess.check_output(['git', 'status', '-s'], encoding='UTF-8', errors='replace') == ''

def check_docker_daemon(*_, **__):
    result = subprocess.run(['docker', 'version'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=False, encoding='UTF-8',
                            errors='replace')
    return result.returncode == 0

def check_utf_encoding(*_, **__):
    if host_platform.is_windows():
        return True
    return locale.getpreferredencoding().lower() == sys.getdefaultencoding().lower() == 'utf-8'

def check_tty_attached(*_, **__):
    return not sys.stdin.isatty()


def check_swap_disabled(*_, **__):

    if host_platform.is_windows():
        result = subprocess.check_output(
            ['powershell', '-NonInteractive', '-NoProfile', '-Command',
             'Get-WmiObject Win32_PageFileUsage | Measure-Object | Select-Object -ExpandProperty Count'],
            encoding='utf-8', errors='replace'
        )
        return result.strip() == '0'

    if host_platform.is_macos():
        result = subprocess.check_output(['sysctl', 'vm.swapusage'], encoding='utf-8', errors='replace')
        return result.strip() == 'vm.swapusage: total = 0.00M  used = 0.00M  free = 0.00M  (encrypted)'

    result = subprocess.check_output(['free'], encoding='utf-8', errors='replace')
    for line in result.splitlines():
        # we want this output: Swap:              0           0           0
        # and condense it to Swap:000
        if line.startswith('Swap') and line.replace(' ', '') != 'Swap:000':
            return False
    return True


def check_suspend(*, run_duration):
    run_duration = math.ceil(run_duration/1e6)

    if host_platform.is_windows():
        # Event ID 42 (Kernel-Power) is logged when the system enters sleep/suspend
        command = [
            'powershell', '-NoProfile', '-Command',
            f"Get-WinEvent -FilterHashtable @{{LogName='System'; Id=42; StartTime=(Get-Date).AddSeconds(-{run_duration})}} -ErrorAction SilentlyContinue | Measure-Object | Select-Object -ExpandProperty Count"
        ]
        ps = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, encoding='UTF-8', errors='replace')
        if ps.stderr:
            raise RuntimeError(f"Could not check for system suspend state: {ps.stderr}")
        return ps.stdout.strip() == '0'


    if host_platform.is_macos(): # no NTP for darwin, as this is linux cluster only functionality
        command = [f"log show --style syslog --predicate 'eventMessage contains[c] \"Entering sleep\" OR eventMessage contains[c] \"Entering Sleep\"' --last {run_duration}s --info --debug | tail -n+1 | grep -v 'log run noninteractively'"]
    else:
        command = [f"journalctl --grep='suspend' --output=short-iso --since '{run_duration} seconds ago' -q"]

    ps = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=True,
        encoding='UTF-8',
        errors='replace'
    )
    if ps.stderr:
        raise RuntimeError(f"Could not check for system suspend state: {ps.stderr}")

    return 'Entering' not in ps.stdout and 'suspend' not in ps.stdout

def check_steal_time(*_, **__):
    if host_platform.is_windows():
        return True
    return math.isclose(getattr(psutil.cpu_times(), 'steal', 0.0), 0.0, abs_tol=1e-6) # safe check for float == 0.0


@functools.cache
def _get_sudo_check_results():
    sudo_script = Path('/usr/local/bin/green-metrics-tool/system_checks_root.py')
    if not sudo_script.exists():
        return {}

    python_realpath = Path(sys.executable).resolve()
    result = subprocess.run(
        ['sudo', python_realpath.as_posix(), '-I', '-B', '-S', sudo_script.as_posix()],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding='UTF-8', errors='replace', check=False,
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

    if '_check_error' in data:
        err = data['_check_error']
        raise ConfigurationCheckError(err['message'], Status[err['status']])

    if result.returncode != 0:
        return {}

    return data


def _parse_timers(data):
    '''Parse systemctl list-timers output; returns list of found timer entries (empty = OK).'''
    if re.search(r'^0 timers listed\.$', data, re.MULTILINE):
        return []
    return [
        el.strip() for el in data.splitlines()
        if el.strip() and not el.strip().startswith('NEXT')
        and not el.strip().startswith('-') and not el.strip().endswith('timers listed.')
    ]


def check_systemd_timers(*_, **__):
    if platform.system() in ('Darwin', 'Windows'):
        return True

    data = _get_sudo_check_results()
    if not data:
        return None  # sudo script not installed or failed — skip
    timers = data.get('systemd_timers', {})
    if 'error' in timers and not timers.get('system_timers'):
        return None  # systemctl unavailable — skip
    if timers.get('system_timers'):
        return False

    result = subprocess.run(
        ['systemctl', '--user', '--all', 'list-timers'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        encoding='UTF-8', errors='replace', check=False,
    )
    if result.returncode != 0:
        return None  # user session unavailable — skip
    return not _parse_timers(result.stdout)


def check_cron_files(*_, **__):
    if platform.system() in ('Darwin', 'Windows'):
        return True

    data = _get_sudo_check_results()
    if not data:
        return None  # sudo script not installed or failed — skip
    cron = data.get('cron_files', {})
    if 'error' in cron and not cron.get('files_found'):
        return None  # find unavailable — skip
    return not cron.get('files_found')


def _check_rapl_domain(domain_key):
    '''Shared logic for per-domain RAPL power capping checks.

    domain_key must be one of 'package', 'dram', or 'psys'.
    Checks that both the long_term and short_term power limits (whichever are present on
    the domain) are exactly equal to the configured value — this also transitively catches
    long_term/short_term disagreeing with each other, without needing a separate check.
    Returns True (all limits match), False (at least one domain's limit is missing or does
    not match the configured cap), or None (check skipped — not configured, sudo
    unavailable, or RAPL not present).
    '''
    if platform.system() in ('Darwin', 'Windows'):
        return True
    config = GlobalConfig().config
    rapl_cfg = config.get('machine', {}).get('rapl_power_capping')
    if not rapl_cfg or not isinstance(rapl_cfg, dict):
        return NOT_CONFIGURED  # rapl_power_capping not configured at all — skip
    expected_watts = rapl_cfg.get(domain_key)
    if not expected_watts:
        return NOT_CONFIGURED  # this specific domain not configured — skip
    data = _get_sudo_check_results()
    if not data:
        return None  # sudo script not installed or failed — skip
    rapl_limits = data.get('rapl_power_limits', {})
    if isinstance(rapl_limits, dict) and 'error' in rapl_limits:
        return None  # RAPL read failed — skip
    domain_entries = rapl_limits.get(domain_key, [])
    if not domain_entries:
        return False  # configured in config but no matching RAPL domain found on machine
    expected_uw = int(expected_watts) * 1_000_000
    for entry in domain_entries:
        for limit_key in ('long_term_uw', 'short_term_uw'):
            value = entry.get(limit_key)
            if value is None:
                continue  # this constraint type not exposed on this domain — skip it
            if not str(value).isdigit() or int(value) != expected_uw:
                return False
    return True


def check_rapl_power_capping_package(*_, **__):
    return _check_rapl_domain('package')


def check_rapl_power_capping_dram(*_, **__):
    return _check_rapl_domain('dram')


def check_rapl_power_capping_psys(*_, **__):
    return _check_rapl_domain('psys')


def check_docker_registry_url(*_, **__):
    config = GlobalConfig().config
    expected_url = config.get('machine', {}).get('docker_registry_url')
    if expected_url is None:
        return NOT_CONFIGURED
    result = subprocess.run(
        ['docker', 'info'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding='UTF-8', errors='replace', check=False,
    )
    if result.returncode != 0:
        return None  # docker not reachable — let check_docker_daemon report that
    if expected_url is False:
        return 'Registry Mirrors:' not in result.stdout  # confirmed no registry mirror is configured
    normalized = expected_url.rstrip('/')
    return normalized in result.stdout or (normalized + '/') in result.stdout


def check_cpu_cores(*_, **__):
    expected = GlobalConfig().config.get('machine', {}).get('cpu_cores')
    if not expected:
        return NOT_CONFIGURED
    return psutil.cpu_count(logical=True) == int(expected)


def check_dram(*_, **__):
    if platform.system() in ('Darwin', 'Windows'):
        return None  # lsmem is a Linux (util-linux) only tool
    expected_gb = GlobalConfig().config.get('machine', {}).get('dram_gb')
    if not expected_gb:
        return NOT_CONFIGURED
    result = subprocess.run(
        ['lsmem', '--bytes', '--summary=only'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding='UTF-8', errors='replace', check=False,
    )
    if result.returncode != 0:
        return None  # lsmem unavailable — skip

    # installed memory = online + offline blocks, so hot-removed/offline DIMMs are still counted
    total_bytes = 0
    found = False
    for line in result.stdout.splitlines():
        match = re.match(r'Total (online|offline) memory:\s*(\d+)', line.strip())
        if match:
            total_bytes += int(match.group(2))
            found = True
    if not found:
        return None  # unexpected lsmem output — skip

    actual_gb = round(total_bytes / (1024 ** 3))
    return actual_gb == int(expected_gb)


def check_usb_devices(*_, **__):
    if platform.system() in ('Darwin', 'Windows'):
        return None
    allowlist = GlobalConfig().config.get('machine', {}).get('usb_devices')
    if not allowlist:
        return NOT_CONFIGURED
    result = subprocess.run(
        ['lsusb'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding='UTF-8', errors='replace', check=False,
    )
    if result.returncode != 0:
        return None  # lsusb not available — skip
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        if not any(entry in line for entry in allowlist):
            return False  # unexpected device found
    return True


def check_pci_devices(*_, **__):
    if platform.system() in ('Darwin', 'Windows'):
        return None
    allowlist = GlobalConfig().config.get('machine', {}).get('pci_devices')
    if not allowlist:
        return NOT_CONFIGURED
    result = subprocess.run(
        ['lspci'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding='UTF-8', errors='replace', check=False,
    )
    if result.returncode != 0:
        return None  # lspci not available — skip
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        if not any(entry in line for entry in allowlist):
            return False  # unexpected device found
    return True


def check_cpu_governor(*_, **__):
    if platform.system() in ('Darwin', 'Windows'):
        return None
    expected = GlobalConfig().config.get('machine', {}).get('cpu_governor')
    if expected is None:
        return NOT_CONFIGURED
    gov_dir = '/sys/devices/system/cpu'
    found_any = False
    try:
        for entry in os.listdir(gov_dir):
            gov_path = os.path.join(gov_dir, entry, 'cpufreq', 'scaling_governor')
            if not os.path.isfile(gov_path):
                continue
            found_any = True
            if expected is False:
                return False  # a scaling governor is active, but none was expected
            try:
                with open(gov_path, 'r', encoding='utf-8') as f:
                    if f.read().strip() != expected:
                        return False
            except OSError:
                continue
    except OSError:
        return None
    if expected is False:
        return True  # confirmed no scaling governor is active on any core
    return True if found_any else None


def check_cpu_smt(*_, **__):
    if platform.system() in ('Darwin', 'Windows'):
        return None
    config_val = GlobalConfig().config.get('machine', {}).get('cpu_smt')
    if config_val is None:
        return NOT_CONFIGURED
    smt_path = '/sys/devices/system/cpu/smt/active'
    try:
        with open(smt_path, 'r', encoding='utf-8') as f:
            active = f.read().strip() == '1'
    except OSError:
        return None  # SMT not supported on this CPU — skip
    return active == bool(config_val)


def check_cpu_turbo_boost(*_, **__):
    if platform.system() in ('Darwin', 'Windows'):
        return None
    config_val = GlobalConfig().config.get('machine', {}).get('cpu_turbo_boost')
    if config_val is None:
        return NOT_CONFIGURED
    # Intel pstate: no_turbo=0 means boost is ON
    intel_path = '/sys/devices/system/cpu/intel_pstate/no_turbo'
    try:
        with open(intel_path, 'r', encoding='utf-8') as f:
            boost_on = f.read().strip() == '0'
        return boost_on == bool(config_val)
    except OSError:
        pass
    # Generic cpufreq boost: boost=1 means boost is ON
    generic_path = '/sys/devices/system/cpu/cpufreq/boost'
    try:
        with open(generic_path, 'r', encoding='utf-8') as f:
            boost_on = f.read().strip() == '1'
        return boost_on == bool(config_val)
    except OSError:
        pass
    return None  # no turbo boost interface found — skip


def check_cpu_frequency(*_, **__):
    expected_mhz = GlobalConfig().config.get('machine', {}).get('cpu_frequency_mhz')
    if not expected_mhz:
        return NOT_CONFIGURED
    freqs = psutil.cpu_freq(percpu=True)
    if not freqs:
        return None  # not available on this platform or kernel
    tolerance_mhz = 10
    return all(abs(f.current - int(expected_mhz)) <= tolerance_mhz for f in freqs)


def check_cpu_scaling_driver(*_, **__):
    if platform.system() in ('Darwin', 'Windows'):
        return None
    expected = GlobalConfig().config.get('machine', {}).get('cpu_scaling_driver')
    if expected is None:
        return NOT_CONFIGURED
    cpu_dir = '/sys/devices/system/cpu'
    found_any = False
    try:
        for entry in os.listdir(cpu_dir):
            driver_path = os.path.join(cpu_dir, entry, 'cpufreq', 'scaling_driver')
            if not os.path.isfile(driver_path):
                continue
            found_any = True
            if expected is False:
                return False  # a scaling driver is active, but none was expected
            try:
                with open(driver_path, 'r', encoding='utf-8') as f:
                    if f.read().strip() != expected:
                        return False
            except OSError:
                continue
    except OSError:
        return None
    if expected is False:
        return True  # confirmed no scaling driver is active on any core
    return True if found_any else None


def check_temperature(*_, **__):
    config = GlobalConfig().config
    chip = config.get('machine', {}).get('base_temperature_chip')
    feature = config.get('machine', {}).get('base_temperature_feature')
    base_value = config.get('machine', {}).get('base_temperature_value')

    if not chip or not feature or not base_value:
        return NOT_CONFIGURED

    current_temp = get_temperature(chip, feature)
    DB().query('UPDATE machines SET current_temperature=%s WHERE id = %s',
               params=(current_temp, config['machine']['id']))

    if current_temp > base_value:
        raise TemperatureException(
            f"Machine too hot: {current_temp}° (base: {base_value}°)",
            direction='hot',
            temperature=current_temp,
        )

    if current_temp <= (base_value - 10):
        raise TemperatureException(
            f"Machine too cold: {current_temp}° (base: {base_value}°)",
            direction='cold',
            temperature=current_temp,
        )

    return True


######## END CHECK FUNCTIONS ########

start_checks = (
    (check_temperature, Status.WARN, 'base temperature', 'Machine temperature is out of range. Waiting for temperature to stabilize.'),
    (check_db, Status.ERROR, 'db online', 'This text will never be triggered, please look in the function itself'),
    (check_gmt_dir_dirty, Status.WARN, 'gmt directory dirty', 'The GMT directory contains untracked or changed files - These changes will not be stored and it will be hard to understand possible changes when comparing the measurements later. We recommend only running on a clean dir.'),
    (check_one_energy_and_scope_machine_provider, Status.ERROR, 'single energy scope machine provider', 'Please only select one provider with energy and scope machine'),
    (check_tmpfs_mount, Status.INFO, 'tmpfs mount', 'We recommend to mount tmp on tmpfs'),
    (check_ntp, Status.WARN, 'ntp', 'You have NTP time syncing active. This can create noise in runs and should be deactivated.'),
    (check_cpu_utilization, Status.WARN, '< 5% CPU utilization', 'Your system seems to be busy. Utilization is above 5%. Consider terminating some processes for a more stable measurement.'),
    (check_largest_sampling_rate, Status.WARN, 'high sampling rate', 'You have chosen at least one provider with a sampling rate > 1000 ms. That is not recommended and might lead also to longer benchmarking times due to internal extra sleeps to adjust measurement frames.'),
    (check_available_cpus, Status.ERROR, '< 2 CPUs', 'You need at least 2 CPU cores on the system (and assigned to Docker in case of macOS) to run GMT'),
    (check_docker_cpu_availability, Status.WARN, 'Docker CPU reporting', 'Docker reports a different amount of available CPUs than the host sytem itself - This is expected when Docker is running in VM. In all other cases this will lead to inaccurate cgroup metrics reported.'),
    (check_assignable_cpus, Status.ERROR, 'No assignable cpus', 'GMT does not have any assignable CPUs for the docker containers available. Reserve less CPUs in the config.yml for GMT, increase the CPU count of the Docker VM (in case of macOS) or migrate to a bigger machine.'),
    (check_free_disk, Status.ERROR, '1 GiB free hdd space', 'You need to free up some disk space to run GMT reliably (< 1 GiB available)'),
    (check_free_memory, Status.ERROR, '2 GiB free memory', 'No free memory! Please kill some programs (< 2 GiB available)'),
    (check_assignable_memory, Status.ERROR, 'No assignable memory', 'GMT does not have any assignable memory for the docker containers available. Reserve less memory in the config.yml for GMT, increase the memory amount of the Docker VM (in case of macOS) or migrate to a bigger machine.'),
    (check_assignable_memory_oom, Status.WARN, 'OOM risk', 'Your system available memory is less than what can be assigned to the docker containers. This can lead to the system running into OOM. For development this is fine, but for reliable measurements you should reserve more memory to the host system via "host_reserved_memory" in config.yml.'),
    (check_docker_daemon, Status.ERROR, 'docker daemon', 'The docker daemon could not be reached. Are you running in rootless mode or have added yourself to the docker group? See installation: [See https://docs.green-coding.io/docs/installation/]'),
    (check_docker_host_env, Status.ERROR, 'docker host env', 'You seem to be running a rootless docker and in this case you must set the DOCKER_HOST environment variable so that the docker library we use can find the docker agent. Typically this should be DOCKER_HOST=unix:///$XDG_RUNTIME_DIR/docker.sock'),
    (check_containers_running, Status.WARN, 'running containers', 'You have other containers running on the system. This is usually what you want in local development, but for undisturbed measurements consider going for a measurement cluster [See https://docs.green-coding.io/docs/installation/installation-cluster/].'),
    (check_systemd_timers, Status.WARN, 'systemd timers', 'Unexpected systemd timers are active. These can create interference during measurements. Disable or remove them for reliable cluster benchmarks.'),
    (check_cron_files, Status.WARN, 'cron files', 'Active cron files found in /var/spool/cron or /etc/cron*. These can create interference during measurements. Disable or remove them for reliable cluster benchmarks.'),
    (check_rapl_power_capping_package, Status.WARN, 'rapl power capping (package)', 'RAPL package domain power limit does not match the value configured in machine.rapl_power_capping.package. Verify that the system power cap is set correctly.'),
    (check_rapl_power_capping_dram, Status.WARN, 'rapl power capping (dram)', 'RAPL DRAM domain power limit does not match the value configured in machine.rapl_power_capping.dram. Verify that the system power cap is set correctly.'),
    (check_rapl_power_capping_psys, Status.WARN, 'rapl power capping (psys)', 'RAPL psys domain power limit does not match the value configured in machine.rapl_power_capping.psys. Verify that the system power cap is set correctly.'),
    (check_docker_registry_url, Status.WARN, 'docker registry url', 'Docker registry mirror configuration does not match machine.docker_registry_url (set to false to require that no mirror is configured). Verify the Docker daemon registry-mirrors configuration.'),
    (check_cpu_cores, Status.WARN, 'cpu core count', 'CPU core count does not match machine.cpu_cores. Check for hot-plug events or unexpected SMT/HT state changes.'),
    (check_dram, Status.WARN, 'dram size', 'Total RAM does not match machine.dram_gb. A DIMM may have failed or been removed/added.'),
    (check_usb_devices, Status.WARN, 'usb devices', 'An unexpected USB device is connected. Review the machine.usb_devices allowlist and remove or account for the new device.'),
    (check_pci_devices, Status.WARN, 'pci devices', 'An unexpected PCI device is present. Review the machine.pci_devices allowlist and remove or account for the new card.'),
    (check_cpu_governor, Status.WARN, 'cpu governor', 'At least one CPU core is not using the expected scaling governor set in machine.cpu_governor (set to false to require that no scaling governor is active). This can cause significant measurement variance.'),
    (check_cpu_smt, Status.WARN, 'cpu smt', 'Hyper-Threading / SMT state does not match machine.cpu_smt. This affects core count and benchmark reproducibility.'),
    (check_cpu_turbo_boost, Status.WARN, 'cpu turbo boost', 'CPU turbo boost state does not match machine.cpu_turbo_boost. Unexpected boost can cause power and timing variance in measurements.'),
    (check_cpu_frequency, Status.WARN, 'cpu frequency', 'At least one CPU core is running outside ±10 MHz of the frequency set in machine.cpu_frequency_mhz. Verify that CPU frequency scaling is locked correctly.'),
    (check_cpu_scaling_driver, Status.WARN, 'cpu scaling driver', 'CPU scaling driver does not match machine.cpu_scaling_driver (set to false to require that no scaling driver is active). A different driver may apply different power and frequency policies.'),
    (check_utf_encoding, Status.ERROR, 'utf file encoding', 'Your system encoding is not set to utf-8. This is needed as we need to parse console output.'),
    (check_swap_disabled, Status.WARN, 'swap disabled', 'Your system uses a swap filesystem. This can lead to very instable measurements. Please disable swap.'),
    (check_tty_attached, Status.WARN, 'tty attached', 'GMT runs with a TTY attached. This will create relevant overhead. This is usually what you want in local development, but for undisturbed measurements consider going for a measurement cluster [See https://docs.green-coding.io/docs/installation/installation-cluster/].'),
)

end_checks = (
    (check_suspend, Status.ERROR, 'system suspend', 'System has gone into suspend during measurement. This will skew all measurement data. If GMT shall ever be able to correctly account for suspend states please note that metric providers must support CLOCK_BOOTIME. See https://github.com/green-coding-solutions/green-metrics-tool/pull/1229 for discussion.'),
    (check_steal_time, Status.ERROR, 'cpu steal time', 'The CPU has accounted steal time. This means the measurement could have been interrupted and / or the VM that you are running in halted. This will lead to broken measurement data as time jumps can occur.'),

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
            if retval is NOT_CONFIGURED:
                output = f"{TerminalColors.OKCYAN}INFO{TerminalColors.ENDC} (Skipped: not configured in config.yml)"
            elif retval or retval is None:
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
