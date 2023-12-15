#!/bin/bash

echo "apt-daily-upgrade"
/usr/lib/apt/apt.systemd.daily update

echo "apt-daily"
/usr/lib/apt/apt.systemd.daily install

echo "dpkg-db-backup"
/usr/libexec/dpkg/dpkg-db-backup

echo "e2scrub_all"
/sbin/e2scrub_all

echo "fstrim"
/sbin/fstrim --listed-in /etc/fstab:/proc/self/mountinfo --verbose --quiet-unsupported

echo "systemd-tmpfiles-clean"
systemd-tmpfiles --clean

echo "logrotate"
/usr/sbin/logrotate /etc/logrotate.conf

echo "systemd-journal-flush"
journalctl --flush
