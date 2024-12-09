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
    # This will try to capture one packet only. However since no network traffic might be happening we also limit to 5 seconds
    first_line=$(timeout 3 tcpdump -tt --micro -n -v -c 1)
    # timeout will raise error code 124
    if [ $? -eq 1 ]; then
        echo "tcpdump could not be started. Missing sudo permissions?"
        exit 1
    fi
    exit 0
fi

tcpdump -tt --micro -n -v
