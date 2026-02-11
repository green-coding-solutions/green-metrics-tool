import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os
import re
import time
import subprocess
import argparse

def _parse_timers(data):
    if not re.search(r'^0 timers listed.$', data, re.MULTILINE):
        for el in data.splitlines():
            el = el.strip()
            if el == '' or el.startswith('NEXT') or el.startswith('-') or el.endswith('timers listed.'):
                pass
            else:
                raise RuntimeError('Found timer', el, '\n', 'Stdout dump:', data)

def cleanup():
    # We can NEVER include non system packages here, as we rely on them all being writeable by root only.
    # This will only be true for non-venv pure system packages coming with the python distribution of the OS

    # always
    commands = [
        ['/usr/libexec/dpkg/dpkg-db-backup'],
        ['/sbin/e2scrub_all'],
        ['/sbin/fstrim', '--listed-in', '/etc/fstab:/proc/self/mountinfo', '--verbose', '--quiet-unsupported'],
        ['systemd-tmpfiles', '--clean'],
        ['/usr/sbin/logrotate', '/etc/logrotate.conf'],
        ['journalctl', '--flush']
    ]
    for command in commands:
        print('Running', command)
        ps = subprocess.run(
            ['sudo', *command],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # put both in one stream
            encoding='UTF-8',
            errors='replace',
        )
        if ps.returncode != 0:
            raise RuntimeError(f"{command} failed: {ps.stdout}")

def sync_ntp():
    ## Update time
    # may throw exception, but we need to check if time sync calls work, as we do not know what the actual time is
    # Typically in cluster installations port 123 is blocked and a local time server is available. Thus the guard function here
    subprocess.check_output(['sudo', 'timedatectl', 'set-ntp', 'true'], encoding='UTF-8', errors='replace') # this will trigger immediate update
    time.sleep(5)
    ntp_status = subprocess.check_output(['timedatectl', '-a'], encoding='UTF-8', errors='replace')
    if 'System clock synchronized: yes' not in ntp_status or 'NTP service: active' not in ntp_status:
        raise RuntimeError('System clock could not be synchronized', ntp_status)

    subprocess.check_output(['sudo', 'timedatectl', 'set-ntp', 'false'], encoding='UTF-8', errors='replace') # we want NTP always off in clusters
    time.sleep(2)
    ntp_status = subprocess.check_output(['timedatectl', '-a'], encoding='UTF-8', errors='replace')
    if 'System clock synchronized: yes' not in ntp_status:
        raise RuntimeError('System clock synchronization could not be synchronized', ntp_status)

    if 'NTP service: inactive' not in ntp_status:
        raise RuntimeError('System clock synchronization could not be turned off', ntp_status)

def check_systemd_timers():
    # List all timers and services to validate we have nothing left

    result = subprocess.run(
        ['sudo', 'systemctl', '--all', 'list-timers'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # put both in one stream
        encoding='UTF-8', errors='replace', check=True)

    _parse_timers(result.stdout)

    print('Checking user timers for', os.environ['SUDO_USER'])

    result = subprocess.run(
        ['sudo', 'systemctl', f"--machine={os.environ['SUDO_USER']}@", '--user', '--all', 'list-timers'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # put both in one stream
        encoding='UTF-8', errors='replace', check=True)

    _parse_timers(result.stdout)

def update_os_packages():
    ## Do APT last, as we want to insert the Changelog
    apt_packages_upgrade = None
    ps = subprocess.run(
        ['sudo', 'apt', 'update'],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # put both in one stream
        encoding='UTF-8',
        errors='replace'
    )
    if ps.returncode != 0:
        raise RuntimeError(f"sudo apt update failed: {ps.stdout}")


    apt_packages_upgrade = subprocess.check_output(['apt', 'list', '--upgradeable'], encoding='UTF-8', errors='replace', stderr=subprocess.DEVNULL).split('\n')[1:]

    if apt_packages_upgrade == ['']:
        apt_packages_upgrade = None
    else:
        ps = subprocess.run(
            [
                'sudo', 'apt-get',
                '-o', 'APT::Get::Always-Include-Phased-Updates=true',
                '-o', 'Dpkg::Options::=--force-confdef',
                '-o', 'Dpkg::Options::=--force-confold',
                '-o', 'Acquire::Retries=3',
                'full-upgrade', '-y'
            ],
            check=False,
            env={'DEBIAN_FRONTEND': 'noninteractive'},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # put both in one stream
            encoding='UTF-8',
            errors='replace'
        )
        if ps.returncode != 0:
            raise RuntimeError(f"sudo apt full-upgrade -y failed: {ps.stdout}")

    if apt_packages_upgrade:
        print('<<<< UPDATED APT PACKAGES >>>>')
        print(apt_packages_upgrade)
        print('<<<< END UPDATED APT PACKAGES >>>>')
    else:
        print('<<<< NO PACKAGES UPDATED - NO NEED TO RUN VALIDATION WORKLOAD >>>>')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--update-os-packages', action='store_true', help='Update OS Packages during maintenance job')
    args = parser.parse_args()

    cleanup()
    sync_ntp()
    check_systemd_timers()

    if args.update_os_packages:
        update_os_packages()
