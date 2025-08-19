#!/usr/bin/env bash

## Run git bisect beforehand with
# $ git bisect start
# $ git bisect good <commit-good>
# $ git bisect bad <commit-bad>

# Then
# git bisect run ./bisect-script.sh

cd tests # Since git will execute stuff always from the repository root, but tests expect to be run from the test dir we need to cd
source ../venv/bin/activate
python3 setup-test-env.py --ee && bash stop-test-containers.sh && bash start-test-containers.sh -d
sleep 2 # test containers must first instantiate DB
pytest lib/test_phase_stats.py::test_phase_stats_network_io_two_measurements_at_phase_border
