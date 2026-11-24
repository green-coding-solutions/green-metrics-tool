#!/usr/bin/env bash
# Smoke test for the prebuilt GMT frontend image. Used by the CI workflow and runnable locally:
#   docker build -f docker/frontend-image/Dockerfile -t gmt-frontend:test .
#   ./docker/frontend-image/test-image.sh gmt-frontend:test
set -euo pipefail

IMAGE=${1:?Usage: $0 IMAGE}
CONFIG_PATH=/var/www/green-metrics-tool/frontend/js/helpers/config.js

containers=()
tmp_dir=$(mktemp -d)

cleanup() {
    if [[ ${#containers[@]} -gt 0 ]]; then
        docker rm -f "${containers[@]}" > /dev/null 2>&1 || true
    fi
    rm -rf "$tmp_dir"
}
trap cleanup EXIT

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

# Sets URL to the base URL of the container once nginx answers
wait_for_nginx() {
    local port
    port=$(docker port "$CID" 9142/tcp | head -n 1 | sed 's/.*://')
    URL="http://127.0.0.1:${port}"
    # The docker port proxy resets connections until nginx listens, hence --retry-all-errors
    if ! curl -fsS -o /dev/null --retry 15 --retry-all-errors --retry-delay 1 "${URL}/"; then
        docker logs "$CID" >&2
        fail "nginx did not come up"
    fi
}

# Starts a container and sets CID and URL. Not meant to run in a subshell, as the
# container must be registered for the cleanup.
start() {
    CID=$(docker run -d -p 127.0.0.1::9142 "$@" "$IMAGE")
    containers+=("$CID")
    wait_for_nginx
}

assert_contains() {
    grep -qF -- "$2" <<< "$1" || fail "expected '$2' in:"$'\n'"$1"
}

# Expects the container to stop with an error before nginx starts
assert_start_fails() {
    local cid state
    cid=$(docker run -d "$@" "$IMAGE")
    containers+=("$cid")
    for _ in $(seq 1 15); do
        state=$(docker inspect -f '{{.State.Running}} {{.State.ExitCode}}' "$cid")
        if [[ $state == "false "* ]]; then
            [[ $state != "false 0" ]] || fail "container exited with 0 for: $*"
            return 0
        fi
        sleep 1
    done
    fail "container kept running for: $*"
}

echo "Test 1: config.js from environment variables"
start \
    -e GMT_API_URL='https://api.example.com/x?a=1&b=2|3' \
    -e GMT_METRICS_URL=https://metrics.example.com \
    -e GMT_ACTIVATE_ECO_CI=TRUE \
    -e GMT_ACTIVATE_CARBON_DB=0
config=$(curl -fsS "${URL}/js/helpers/config.js")
assert_contains "$config" 'API_URL = "https://api.example.com/x?a=1&b=2|3"'
assert_contains "$config" 'METRICS_URL = "https://metrics.example.com"'
assert_contains "$config" 'ELEPHANT_URL = ""'
assert_contains "$config" 'ACTIVATE_SCENARIO_RUNNER = true;'
assert_contains "$config" 'ACTIVATE_ECO_CI = true;'
assert_contains "$config" 'ACTIVATE_CARBON_DB = false;'
assert_contains "$config" 'ACTIVATE_POWER_HOG = false;'
assert_contains "$config" 'const total_chart_bottom_condition'
if grep -qE '__[A-Z_]+__' <<< "$config"; then
    fail "placeholders left in generated config.js"
fi
curl -fsS "${URL}/index.html" | grep -q '/js/helpers/config.js' || fail "index.html not served"
code=$(curl -s -o /dev/null -w '%{http_code}' "${URL}/js/helpers/config.js.example")
[[ $code == 404 ]] || fail "config.js.example is served (HTTP $code)"

echo "Test 2: config.js is regenerated after a restart"
docker restart "$CID" > /dev/null
wait_for_nginx
if docker logs "$CID" 2>&1 | grep -q 'Using mounted'; then
    fail "generated config.js was taken for a mounted one after the restart"
fi

echo "Test 3: mounted config.js is served as it is"
printf 'API_URL = "https://mounted.example.com"\n// custom\n' > "${tmp_dir}/config.js"
chmod 644 "${tmp_dir}/config.js"
start -v "${tmp_dir}/config.js:${CONFIG_PATH}:ro" -e GMT_API_URL=https://ignored.example.com
config=$(curl -fsS "${URL}/js/helpers/config.js")
[[ $config == "$(cat "${tmp_dir}/config.js")" ]] || fail "mounted config.js was changed:"$'\n'"$config"

echo "Test 4: invalid values stop the container"
assert_start_fails -e GMT_ACTIVATE_ECO_CI=maybe
assert_start_fails -e 'GMT_API_URL=https://example.com/"+alert(1)+"'
assert_start_fails -v "${tmp_dir}/does-not-exist:${CONFIG_PATH}"

echo "All frontend image tests passed"
