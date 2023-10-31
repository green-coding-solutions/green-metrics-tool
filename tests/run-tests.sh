#!/bin/bash
echo "Starting test containers..."
./start-test-containers.sh &>/dev/null &
sleep 2
echo "Running pytest..."
pytest
echo "Stopping test containers..."
./stop-test-containers.sh  &>/dev/null &
echo "fin"