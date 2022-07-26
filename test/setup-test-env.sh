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
    read -sp "Please enter the new password to be set for the testing PostgreSQL DB: " db_pw
fi

echo "Updating config.yml with new password ..."
cp ../config.yml.example ../test-config.yml
sed -i -e "s|host: |host: test-|" ../test-config.yml
sed -i -e "s|PLEASE_CHANGE_THIS|$db_pw|" ../test-config.yml

echo "Creating test-compose.yml ..."
cp ../docker/compose.yml.example ../docker/test-compose.yml
sed -i -e "s|PATH_TO_GREEN_METRICS_TOOL_REPO|$PWD/../|" ../docker/test-compose.yml
sed -i -e "s|PLEASE_CHANGE_THIS|$db_pw|" ../docker/test-compose.yml
sed -i -e "s|# - TEST_CONFIG_SETUP|- $PWD/../test-config.yml|" ../docker/test-compose.yml

sed -i -e "s|container_name: |container_name: test-|" ../docker/test-compose.yml
sed -i -e "s|green-coding-postgres-data|green-coding-postgres-test-data|" ../docker/test-compose.yml

etc_hosts_line_1="127.0.0.1 test-green-coding-postgres-container"


echo "Writing to /etc/hosts file..."
if ! sudo grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
    echo $etc_hosts_line_1 | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi