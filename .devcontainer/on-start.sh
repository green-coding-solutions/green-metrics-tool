#!/bin/bash
set -euo pipefail

etc_hosts_line_1="127.0.0.1 green-coding-postgres-container"

echo "Writing to /etc/hosts file..."

# Entry 1 is needed for the local resolution of the containers through the jobs.py and runner.py
if ! sudo grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
    echo "$etc_hosts_line_1" | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi

# Ensure that after a restart of the Codespace the ports are set to public again
gh codespace ports visibility 9142:public -c $CODESPACE_NAME
gh codespace ports visibility 9143:public -c $CODESPACE_NAME
