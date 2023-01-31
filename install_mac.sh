#!/bin/bash
set -euo pipefail

db_pw=''
while getopts "p:" o; do
    case "$o" in
        p)
            db_pw=${OPTARG}
            ;;
    esac
done

if [[ -z "$db_pw" ]] ; then
    read -sp "Please enter the new password to be set for the PostgreSQL DB: " db_pw
fi

echo "Updating compose.yml with current path ..."
cp docker/compose.yml.example docker/compose.yml
sed -i -e "s|PATH_TO_GREEN_METRICS_TOOL_REPO|$PWD|" docker/compose.yml
sed -i -e "s|PLEASE_CHANGE_THIS|$db_pw|" docker/compose.yml

echo "Updating config.yml with new password ..."
cp config.yml.example config.yml
sed -i -e "s|PLEASE_CHANGE_THIS|$db_pw|" config.yml

echo "Adding hardware_info_root.py to sudoers file"
echo "ALL ALL=(ALL) NOPASSWD:/usr/bin/powermetrics" | sudo tee /etc/sudoers.d/green_coding_powermetrics
echo "ALL ALL=(ALL) NOPASSWD:/usr/bin/killall powermetrics" | sudo tee /etc/sudoers.d/green_coding_kill_powermetrics


etc_hosts_line_1="127.0.0.1 green-coding-postgres-container"
etc_hosts_line_2="127.0.0.1 api.green-coding.local metrics.green-coding.local"

echo "Writing to /etc/hosts file..."
if ! sudo grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
    echo "$etc_hosts_line_1" | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi

if ! sudo grep -Fxq "$etc_hosts_line_2" /etc/hosts; then
    echo "$etc_hosts_line_2" | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi
