#! /bin/bash
set -euo pipefail

check_system=false
while getopts "c" o; do
    case "$o" in
        c)
            check_system=true
            ;;
    esac
done


if $check_system; then
    # This will try to capture one packet only. However since no network traffic might be happening we also limit to 3 seconds
    # set -e must not abort here, as a timeout (exit code 124) on a quiet network is a valid outcome
    exit_code=0
    timeout 3 tcpdump -tt --micro -n -v -c 1 > /dev/null || exit_code=$?
    if [ $exit_code -ne 0 ] && [ $exit_code -ne 124 ]; then
        echo "tcpdump could not be started. Missing sudo permissions? Exit code: ${exit_code}" >&2
        exit 1
    fi
    exit 0
fi

tcpdump -tt --micro -n -v
