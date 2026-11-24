#!/usr/bin/env bash
# Smoke test for the prebuilt GMT postgres image. Used by the CI workflow and runnable locally:
#   docker build -f docker/postgres-image/Dockerfile -t gmt-postgres:test .
#   ./docker/postgres-image/test-image.sh gmt-postgres:test
set -euo pipefail

IMAGE=${1:?Usage: $0 IMAGE}
PASSWORD=test-password

cid=""
cleanup() {
    if [[ -n $cid ]]; then
        docker rm -f "$cid" > /dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

fail() {
    echo "FAIL: $*" >&2
    if [[ -n $cid ]]; then
        docker logs "$cid" >&2 || true
    fi
    exit 1
}

# Connects over TCP with sslmode=require, like the API and the runner do
query() {
    docker exec -e PGPASSWORD="$PASSWORD" "$cid" \
        psql "host=127.0.0.1 port=9573 user=postgres dbname=green-coding sslmode=require" \
        -v ON_ERROR_STOP=1 -tAc "$1"
}

assert_query() {
    local result
    result=$(query "$1") || fail "query failed: $1"
    [[ $result == "$2" ]] || fail "expected '$2' for '$1', got '$result'"
}

echo "Test 1: the server starts and initialises the schema"
cid=$(docker run -d -e POSTGRES_PASSWORD="$PASSWORD" "$IMAGE")
# During initialisation postgres only listens on the unix socket. TCP answers once all init
# files ran without error (the entrypoint stops on the first SQL error) and the server restarted.
for _ in $(seq 1 60); do
    if [[ $(docker inspect -f '{{.State.Running}}' "$cid") != true ]]; then
        fail "container stopped during initialisation"
    fi
    if docker exec "$cid" pg_isready -q -h 127.0.0.1 -p 9573; then
        break
    fi
    sleep 1
done
docker exec "$cid" pg_isready -q -h 127.0.0.1 -p 9573 || fail "postgres did not come up on port 9573"

echo "Test 2: SSL is on, as the API connects with sslmode=require"
assert_query "SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid()" "t"

echo "Test 3: schema, extensions and seed data are there"
assert_query "SELECT count(*) FROM pg_extension WHERE extname = 'moddatetime'" "1"
assert_query "SELECT count(*) > 0 FROM users" "t"
assert_query "SELECT count(*) > 0 FROM machines" "t"
assert_query "SELECT count(*) > 0 FROM categories" "t"
assert_query "SELECT count(*) FROM runs" "0"

echo "All postgres image tests passed"
