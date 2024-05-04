#!/bin/bash
set -euo pipefail

echo "Running docker containers..."

detach=false

while getopts "d" opts; do
    case "$opts" in
        d) detach=true;;
    esac
done

# docker compose with -f flag if force is true
echo $detach

if [ "$detach" = true ] ; then
    docker compose -f ../docker/test-compose.yml up -d --remove-orphans 
else
    docker compose -f ../docker/test-compose.yml up --remove-orphans
fi