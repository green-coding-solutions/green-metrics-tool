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
subprocess.check_output(['sudo', '/usr/libexec/dpkg/dpkg-db-backup'])

subprocess.check_output(['sudo', '/sbin/e2scrub_all'])

subprocess.check_output(['sudo', '/sbin/fstrim', '--listed-in', '/etc/fstab:/proc/self/mountinfo', '--verbose', '--quiet-unsupported'])

subprocess.check_output(['sudo', 'systemd-tmpfiles', '--clean'])

subprocess.check_output(['sudo', '/usr/sbin/logrotate', '/etc/logrotate.conf'])

subprocess.check_output(['sudo', 'journalctl', '--flush'])

## Update time
# may throw exception, but we need to check if time sync calls work, as we do not know what the actual time is
# Typically in cluster installations port 123 is blocked and a local time server is available. Thus the guard function here
subprocess.check_output(['sudo', 'timedatectl', 'set-ntp', 'true']) # this will trigger immediate update
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
    subprocess.check_output(['sudo', 'apt', 'update'])

    apt_packages_upgrade = subprocess.check_output(['apt', 'list', '--upgradable'], encoding='UTF-8')

    subprocess.check_output(['sudo', 'apt', 'full-upgrade', '-y'])

if apt_packages_upgrade:
    print('<<<< UPDATED APT PACKAGES >>>>')
    print(apt_packages_upgrade)
    print('<<<< END UPDATED APT PACKAGES >>>>')

else:
    print('<<<< NO PACKAGES UPDATED - NO NEED TO RUN VALIDATION WORKLOAD >>>>')
