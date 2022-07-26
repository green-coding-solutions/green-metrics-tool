#!/bin/bash
if [[ -f "../config.yml" ]]; then
    echo "creating config.yml backup..."
    cp ../config.yml ../config.yml.bak
fi

if [[ -f "../test-config.yml" ]]; then
    echo "using test-config.yml..."
    cp ../test-config.yml ../config.yml
fi

echo "Starting test containers..."
./start-test-containers.sh &>/dev/null &
sleep 5
echo "Running pytest..."
pytest
echo "Stopping test containers..."
./stop-test-containers.sh  &>/dev/null &

if [[ -f "../config.yml.bak" ]]; then
    echo "restore config.yml..."
    cp ../config.yml.bak ../config.yml
    rm ../config.yml.bak
fi

echo "fin"