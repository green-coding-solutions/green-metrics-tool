#!/usr/bin/env python3
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os
import time
import subprocess

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
    )
    if ps.returncode != 0:
        raise RuntimeError(f"{command} failed: {ps.stdout}")

## Update time
# may throw exception, but we need to check if time sync calls work, as we do not know what the actual time is
# Typically in cluster installations port 123 is blocked and a local time server is available. Thus the guard function here
subprocess.check_output(['sudo', 'timedatectl', 'set-ntp', 'true']) # this will trigger immediate update
time.sleep(5)
ntp_status = subprocess.check_output(['timedatectl', '-a'], encoding='UTF-8')
if 'System clock synchronized: yes' not in ntp_status or 'NTP service: active' not in ntp_status:
    raise RuntimeError('System clock could not be synchronized', ntp_status)

result = subprocess.check_output(['sudo', 'timedatectl', 'set-ntp', 'false']) # we want NTP always off in clusters
ntp_status = subprocess.check_output(['timedatectl', '-a'], encoding='UTF-8')
if 'System clock synchronized: yes' not in ntp_status:
    raise RuntimeError('System clock synchronization could not be synchronized', ntp_status)

if 'NTP service: inactive' not in ntp_status:
    raise RuntimeError('System clock synchronization could not be turned off', ntp_status)

## Do APT last, as we want to insert the Changelog
apt_packages_upgrade = None
now = time.time()
if (not os.path.exists('/var/log/apt/history.log')) or ((now - os.path.getmtime('/var/log/apt/history.log')) > 86400):

    print("history.log is older than 24 hours")
    ps = subprocess.run(
        ['sudo', 'apt', 'update'],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # put both in one stream
        encoding='UTF-8',
    )
    if ps.returncode != 0:
        raise RuntimeError(f"sudo apt update failed: {ps.stdout}")

    apt_packages_upgrade = subprocess.check_output(['apt', 'list', '--upgradable'], encoding='UTF-8')

    ps = subprocess.run(
        ['sudo', 'apt', 'full-upgrade', '-y'],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # put both in one stream
        encoding='UTF-8',
    )
    if ps.returncode != 0:
        raise RuntimeError(f"sudo apt full-upgrade -y failed: {ps.stdout}")

if apt_packages_upgrade:
    print('<<<< UPDATED APT PACKAGES >>>>')
    print(apt_packages_upgrade)
    print('<<<< END UPDATED APT PACKAGES >>>>')

else:
    print('<<<< NO PACKAGES UPDATED - NO NEED TO RUN VALIDATION WORKLOAD >>>>')
