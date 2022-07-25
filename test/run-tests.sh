#!/bin/bash
echo "creating config.yml backup..."
cp ../config.yml ../config.yml.bak

if [[ -f "../test-config.yml" ]]; then
    echo "using test-config.yml..."
    cp ../test-config.yml ../config.yml
fi

echo "Starting test containers..."
./start-test-containers.sh </dev/null &>/dev/null &
sleep 5
echo "Running pytest..."
pytest
echo "Stopping test containers..."
./stop-test-containers.sh </dev/null &>/dev/null &

echo "restore config.yml..."
cp ../config.yml.bak ../config.yml
rm ../config.yml.bak

echo "fin"