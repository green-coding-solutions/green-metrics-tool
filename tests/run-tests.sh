#!/usr/bin/env bash
echo "Starting test containers..."
./start-test-containers.sh &>/dev/null &
sleep 2
echo "Running pytest..."
pytest -n auto --dist=loadgroup
PARALLEL_EXIT_CODE=$?
# these marked tests must run sequentially after, as it restarts the DB which will collide with other parallel tests running
pytest -m serial
SERIAL_EXIT_CODE=$?
echo "Stopping test containers..."
./stop-test-containers.sh  &>/dev/null &
echo "fin"

if [ "$PARALLEL_EXIT_CODE" -ne 0 ] || [ "$SERIAL_EXIT_CODE" -ne 0 ]; then
  exit 1
fi