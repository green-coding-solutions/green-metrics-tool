
#!/bin/bash
set -euo pipefail

# Remove all the packages we don't need
apt-get purge -y --purge snapd cloud-guest-utils cloud-init apport apport-symptoms cryptsetup cryptsetup-bin cryptsetup-initramfs curl gdisk lxd-installer mdadm open-iscsi snapd squashfs-tools ssh-import-id wget xauth unattended-upgrades update-notifier-common python3-update-manager unattended-upgrades needrestart command-not-found cron lxd-agent-loader modemmanager motd-news-config pastebinit packagekit
systemctl daemon-reload
apt autoremove -y --purge
killall unattended-upgrade-shutdown

# Get newest versions of everything
apt update -y && apt upgrade -y

# These are packages that are installed through the update
apt remove -y --purge networkd-dispatcher multipath-tools

apt autoremove -y --purge

# Disable services that might do things
systemctl disable --now apt-daily-upgrade.timer
systemctl disable --now apt-daily.timer
systemctl disable --now dpkg-db-backup.timer
systemctl disable --now e2scrub_all.timer
systemctl disable --now fstrim.timer
systemctl disable --now motd-news.timer
systemctl disable --now systemd-tmpfiles-clean.timer
systemctl disable --now fwupd-refresh.timer
systemctl disable --now logrotate.timer
systemctl disable --now ua-timer.timer
systemctl disable --now man-db.timer

systemctl disable --now systemd-journal-flush.service
systemctl disable --now systemd-timesyncd.service

systemctl disable --now systemd-fsckd.socket
systemctl disable --now systemd-initctl.socket

systemctl disable --now cryptsetup.target

# Packages to install
apt install -y vim

# Setup networking
NET_NAME=$(networkctl list "en*" --no-legend | cut -f 4 -d " ")
cat <<EOT > /etc/systemd/network/en.network
[Match]
Name=$NET_NAME

[Network]
DHCP=ipv4
EOT

# Disable the kernel watchdogs
echo 0 > /proc/sys/kernel/soft_watchdog
echo 0 > /proc/sys/kernel/nmi_watchdog
echo 0 > /proc/sys/kernel/watchdog
echo 0 > /proc/sys/kernel/watchdog_thresh

# Removes the large header when logging in
rm /etc/update-motd.d/*

# Remove all cron files. Cron shouldn't be running anyway but just to be safe
rm /etc/cron.d/*
rm /etc/cron.daily/*

apt autoremove -y --purge
