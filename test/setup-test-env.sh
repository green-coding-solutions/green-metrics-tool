#!/bin/bash
set -euo pipefail


echo "Updating compose.yml with current path ..."
cp ../docker/compose.yml.example ../docker/test-compose.yml
sed -i -e "s|PATH_TO_GREEN_METRICS_TOOL_REPO|$PWD/../|" ../docker/test-compose.yml
sed -i -e "s|PLEASE_CHANGE_THIS|testpw|" ../docker/test-compose.yml

sed -i -e "s|container_name: |container_name: test-|" ../docker/test-compose.yml
sed -i -e "s|green-coding-postgres-data|green-coding-postgres-test-data|" ../docker/test-compose.yml

echo "Updating config.yml with new password ..."
cp ../config.yml.example ../test-config.yml
sed -i -e "s|PLEASE_CHANGE_THIS|testpw|" ../test-config.yml



etc_hosts_line_1="127.0.0.1 test-green-coding-postgres-container"


echo "Writing to /etc/hosts file..."
if ! sudo grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
    echo $etc_hosts_line_1 | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi
