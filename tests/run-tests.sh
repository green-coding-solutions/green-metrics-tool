#!/usr/bin/env bash
set -euo pipefail

parallel=false
pytest_args=()
containers_started=false
parallel_safe_targets=(
    "api/test_api_helpers.py"
    "lib/test_container_compatibility.py::TestNativeCompatibility"
    "lib/test_container_compatibility.py::TestArchitectureCompatibility::TestUnitTests"
    "lib/test_container_compatibility.py::TestPlatformCompatibilityStatus::TestUnitTests"
    "lib/test_diff.py"
    "lib/test_email_helpers.py"
    "lib/test_save_notes.py"
    "lib/test_schema_checker.py"
    "lib/test_db.py::TestWithDbRetryDecorator"
    "metric_providers/test_metric_provider_functions.py"
    "test_internal_sanity.py"
    "test_yml_parsing.py"
)

for arg in "$@"; do
    if [ "$arg" = "--parallel" ]; then
        parallel=true
    else
        pytest_args+=("$arg")
    fi
done

cleanup() {
    if [ "$containers_started" = true ] ; then
        echo "Stopping test containers..."
        ./stop-test-containers.sh &>/dev/null || true
    fi
}

reset_shared_state() {
    echo "Resetting shared test state..."
    PYTHONPATH=.. python -c "from pathlib import Path; from lib.global_config import GlobalConfig; GlobalConfig().override_config(config_location=str(Path('test-config.yml').resolve())); from tests import test_functions as Tests; Tests.reset_db()"
}

trap cleanup EXIT

echo "Starting test containers..."
./start-test-containers.sh &>/dev/null &
containers_started=true
sleep 2

echo "Running pytest..."
if [ "$parallel" = true ] ; then
    echo "Phase 1/2: parallel-safe tests"
    pytest -n auto --dist loadscope "${parallel_safe_targets[@]}"
    reset_shared_state
    echo "Phase 2/2: shared-state tests"
    pytest -m "not parallel_safe" "${pytest_args[@]}"
else
    pytest "${pytest_args[@]}"
fi

echo "fin"
