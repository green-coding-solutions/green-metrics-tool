#!/bin/bash
./start-test-containers.sh&
sleep 5
pytest
./stop-test-containers.sh