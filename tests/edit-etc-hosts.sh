#!/bin/bash
set -euo pipefail

etc_hosts_line_1="127.0.0.1 test-green-coding-postgres-container"

echo "Writing to /etc/hosts file..."
if ! grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
    echo $etc_hosts_line_1 | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi