#!/bin/bash
set -euo pipefail

echo "Running docker containers..."

detach=false

while getopts "d" opts; do
    case "$opts" in
        d) detach=true;;
    esac
done

# The test nginx container is running on port 9143 instead of 9142.
# So the frontend is able to access the correct nginx container, 
# we temporarily change the port in the fronted config.
sed -i 's/9142/9143/' ../frontend/js/helpers/config.js

# docker compose with -f flag if force is true
echo $detach

if [ "$detach" = true ] ; then
    docker compose -f ../docker/test-compose.yml up -d --remove-orphans 
else
    docker compose -f ../docker/test-compose.yml up --remove-orphans
fi

# Revert the change in the frontend config again.
sed -i 's/9143/9142/' ../frontend/js/helpers/config.js
