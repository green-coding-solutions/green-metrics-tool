'''Root-level system checks that require elevated privileges.

Like hardware_info_root_original.py, this script must only use system Python packages
and is installed as root-owned to /usr/local/bin/green-metrics-tool/ to prevent tampering.

Output is JSON: a dict with check results from each root-requiring check.
'''

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os
import json
import re
import subprocess
import platform
from enum import Enum

# We can NEVER include non system packages here, as we rely on them all being writeable by root only.
# This will only be true for non-venv pure system packages coming with the python distribution of the OS

# Mirrors lib/configuration_check_error.py — inlined because this script is stdlib-only.
Status = Enum('Status', ['INFO', 'WARN', 'ERROR'])

# Reimplemented here, as we do not want to include user space libraries which
# is a security risk in a sudo enabled file
class ConfigurationCheckError(Exception):
    def __init__(self, m, s=Status.INFO):
        super().__init__(m)
        self.status = s


def _parse_timers(data):
    '''Parse systemctl list-timers output; returns list of found timer entries (empty = OK).'''
    timers_found = []
    if re.search(r'^0 timers listed\.$', data, re.MULTILINE):
        return timers_found
    for el in data.splitlines():
        el = el.strip()
        if el == '' or el.startswith('NEXT') or el.startswith('-') or el.endswith('timers listed.'):
            continue
        timers_found.append(el)
    return timers_found


def check_systemd_timers():
    '''Check system-wide systemd timers (root required); returns list of any found timers.'''
    result = subprocess.run(
        ['/usr/bin/systemctl', '--all', 'list-timers'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='UTF-8', errors='replace', check=False)
    if result.returncode != 0:
        return {'system_timers': [], 'error': result.stdout}

    return {'system_timers': _parse_timers(result.stdout)}


def check_cron_files():
    '''Check for active cron files under /var/spool/cron and /etc/cron* (root required).

    Returns list of any cron files found (empty = OK).
    '''
    found = []
    for cmd in ('find /var/spool/cron -type f', 'find /etc/cron* -type f'):
        result = subprocess.run(
            cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            encoding='UTF-8', errors='replace', check=False)
        if result.returncode == 0:
            found += [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {'files_found': found}


def read_rapl_power_limits():
    '''Read long-term and short-term (constraint_0/constraint_1) power limits for RAPL domains,
    classified by type.

    Walks the full powercap sysfs tree and uses each domain's "name" file to classify it
    as package, dram, or psys. Other domains (core, uncore, …) are ignored. Each domain's
    constraint_N_name files are read to identify which constraint_N_power_limit_uw is the
    long_term vs short_term limit (not all domains expose both — e.g. dram/psys typically
    only have long_term). Both values are returned as-is; it is intentionally left to the
    caller to decide whether long_term and short_term must agree with each other or with a
    configured value.

    Returns:
        {
          "package": [{"domain": "intel-rapl:0", "long_term_uw": "35000000", "short_term_uw": "56000000"}, ...],
          "dram":    [{"domain": "intel-rapl:0:1", "long_term_uw": "10000000"}, ...],
          "psys":    [{"domain": "intel-rapl:1", "long_term_uw": "65000000"}],
        }
    '''
    rapl_dir = '/sys/devices/virtual/powercap/intel-rapl'
    result = {'package': [], 'dram': [], 'psys': []}

    if not os.path.isdir(rapl_dir):
        return result

    try:
        for (dir_path, _, files) in os.walk(rapl_dir):
            domain = os.path.basename(dir_path)
            if not domain.startswith('intel-rapl:'):
                continue  # skip the root intel-rapl directory itself

            name_path = os.path.join(dir_path, 'name')
            try:
                with open(name_path, 'r', encoding='utf8') as f:
                    domain_name = f.read().strip()
            except (FileNotFoundError, PermissionError, OSError):
                continue

            constraints = {}
            for constraint_name_file in sorted(f for f in files if re.fullmatch(r'constraint_\d+_name', f)):
                idx = constraint_name_file.split('_')[1]
                try:
                    with open(os.path.join(dir_path, constraint_name_file), 'r', encoding='utf8') as f:
                        constraint_type = f.read().strip()
                    with open(os.path.join(dir_path, f'constraint_{idx}_power_limit_uw'), 'r', encoding='utf8') as f:
                        constraints[constraint_type] = f.read().strip()
                except (FileNotFoundError, PermissionError, OSError):
                    continue

            if not constraints:
                continue

            entry = {'domain': domain}
            if 'long_term' in constraints:
                entry['long_term_uw'] = constraints['long_term']
            if 'short_term' in constraints:
                entry['short_term_uw'] = constraints['short_term']

            if domain_name.startswith('package'):
                result['package'].append(entry)
            elif domain_name == 'dram':
                result['dram'].append(entry)
            elif domain_name == 'psys':
                result['psys'].append(entry)
            # core, uncore, etc. are intentionally skipped
    except (FileNotFoundError, PermissionError, OSError):
        pass

    return result


# Each entry: (result_key, check_function, Status, check_name, warn_message)
# Mirrors the start_checks / end_checks tuple pattern in system_checks.py.
root_checks = (
    ('systemd_timers', check_systemd_timers, Status.WARN, 'systemd timers',
     'Unexpected system timers found. Disable them for reliable cluster benchmarks.'),
    ('cron_files', check_cron_files, Status.WARN, 'cron files',
     'Active cron files found. Disable them for reliable cluster benchmarks.'),
    ('rapl_power_limits', read_rapl_power_limits, Status.WARN, 'rapl power limits',
     'Failed to read RAPL power limits.'),
)


if __name__ == '__main__':
    # Must be here and not in header: see hardware_info_root_original.py for rationale.
    os.environ.clear()  # prevent any env var from influencing root-privileged code

    if platform.system() in ('Darwin', 'Windows'):
        print('{}')
    else:
        results = {}
        system_check_threshold = Status.ERROR.value

        try:
            for result_key, check_fn, status, _name, message in root_checks:
                retval = None
                try:
                    retval = check_fn()
                    results[result_key] = retval
                except ConfigurationCheckError as exc:
                    raise exc
                except Exception as exc:  # pylint: disable=broad-except
                    results[result_key] = {'error': str(exc)}
                finally:
                    if retval is False and status.value >= system_check_threshold:
                        raise ConfigurationCheckError(message, status)
        except ConfigurationCheckError as exc:
            results['_check_error'] = {'message': str(exc), 'status': exc.status.name}
            print(json.dumps(results))
            sys.exit(1)

        print(json.dumps(results))
