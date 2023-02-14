#!/bin/bash
set -euo pipefail

function print_message {
    echo ""
    echo "$1"
}

db_pw=''
while getopts "p:" o; do
    case "$o" in
        p)
            db_pw=${OPTARG}
            ;;
    esac
done

read -p "Please enter the desired API endpoint URL: (default: http://api.green-coding.local:9142): " api_url
api_url=${api_url:-"http://api.green-coding.local:9142"}

read -p "Please enter the desired metrics dashboard URL: (default: http://metrics.green-coding.local:9142): " metrics_url
metrics_url=${metrics_url:-"http://metrics.green-coding.local:9142"}

if [[ -z "$db_pw" ]] ; then
    read -sp "Please enter the new password to be set for the PostgreSQL DB: " db_pw
fi


echo "Updating compose.yml with current path ..."
cp docker/compose.yml.example docker/compose.yml
sed -i '' -e "s|PATH_TO_GREEN_METRICS_TOOL_REPO|$PWD|" docker/compose.yml
sed -i '' -e "s|PLEASE_CHANGE_THIS|$db_pw|" docker/compose.yml

echo "Updating config.yml with new password ..."
cp config.yml.example config.yml
sed -i '' -e "s|PLEASE_CHANGE_THIS|$db_pw|" config.yml

print_message "Updating project with provided URLs ..."
sed -i '' -e "s|__API_URL__|$api_url|" config.yml
sed -i '' -e "s|__METRICS_URL__|$metrics_url|" config.yml
cp docker/nginx/api.conf.example docker/nginx/api.conf
host_api_url=`echo $api_url | sed -E 's/^\s*.*:\/\///g'`
host_api_url=${host_api_url%:*}
sed -i '' -e "s|__API_URL__|$host_api_url|" docker/nginx/api.conf
cp docker/nginx/frontend.conf.example docker/nginx/frontend.conf
host_metrics_url=`echo $metrics_url | sed -E 's/^\s*.*:\/\///g'`
host_metrics_url=${host_metrics_url%:*}
sed -i '' -e "s|__METRICS_URL__|$host_metrics_url|" docker/nginx/frontend.conf
cp frontend/js/config.js.example frontend/js/config.js
sed -i '' -e "s|__API_URL__|$api_url|" frontend/js/config.js
sed -i '' -e "s|__METRICS_URL__|$metrics_url|" frontend/js/config.js

echo "Adding hardware_info_root.py to sudoers file"
echo "ALL ALL=(ALL) NOPASSWD:/usr/bin/powermetrics" | sudo tee /etc/sudoers.d/green_coding_powermetrics
echo "ALL ALL=(ALL) NOPASSWD:/usr/bin/killall powermetrics" | sudo tee /etc/sudoers.d/green_coding_kill_powermetrics


etc_hosts_line_1="127.0.0.1 green-coding-postgres-container"
etc_hosts_line_2="127.0.0.1 api.green-coding.local metrics.green-coding.local"

echo "Writing to /etc/hosts file..."
if ! sudo grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
    echo -e "\n$etc_hosts_line_1" | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi

if ! sudo grep -Fxq "$etc_hosts_line_2" /etc/hosts; then
    echo -e "\n$etc_hosts_line_2" | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi

echo "Building / Updating docker containers"
docker compose -f docker/compose.yml down
docker compose -f docker/compose.yml build