#!/bin/bash
set -euo pipefail

metrics_url="http://metrics.green-coding.internal:9143"
host_metrics_url=`echo $metrics_url | sed -E 's/^\s*.*:\/\///g'`
host_metrics_url=${host_metrics_url%:*}

api_url="http://api.green-coding.internal:9142"
host_api_url=`echo $api_url | sed -E 's/^\s*.*:\/\///g'`
host_api_url=${host_api_url%:*}

etc_hosts_line_1="127.0.0.1 green-coding-postgres-container"
etc_hosts_line_2="127.0.0.1 ${host_api_url} ${host_metrics_url}"

print_message "Writing to /etc/hosts file..."

# Entry 1 is needed for the local resolution of the containers through the jobs.py and runner.py
if ! sudo grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
    echo "$etc_hosts_line_1" | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi

# Entry 2 can be external URLs. These should not resolve to localhost if not explcitely wanted
if [[ ${host_metrics_url} == *".green-coding.internal"* ]];then
    if ! sudo grep -Fxq "$etc_hosts_line_2" /etc/hosts; then
        echo "$etc_hosts_line_2" | sudo tee -a /etc/hosts
    else
        echo "Entry was already present..."
    fi
fi