#! /bin/bash
set -euo pipefail

check_system=false
filter=""
while getopts "cf:" o; do
    case "$o" in
        c)
            check_system=true
            ;;
        f)
            filter="$OPTARG"
            ;;
    esac
done


if $check_system; then
    # nsenter (util-linux) is required to resolve container veth interfaces
    if ! command -v nsenter >/dev/null 2>&1; then
        echo "nsenter (util-linux) is required but was not found in PATH."
        exit 1
    fi

    # the 'ifname' BPF filter and per-line interface tagging for '-i any' captures need
    # tcpdump >= 4.99 / libpcap >= 1.9 (LINUX_SLL2)
    required_version="4.99.0"
    found_version=$(tcpdump --version 2>&1 | head -n1 | awk '{print $NF}')
    if [ "$(printf '%s\n%s\n' "$required_version" "$found_version" | sort -V | head -n1)" != "$required_version" ]; then
        echo "tcpdump >= $required_version is required for 'ifname'/'any' interface tagging support, found $found_version."
        exit 1
    fi

    # This will try to capture one packet only. However since no network traffic might be happening we also limit to 5 seconds
    first_line=$(timeout 3 tcpdump -tt --micro -nn -v -c 1)
    # timeout will raise error code 124
    if [ $? -eq 1 ]; then
        echo "tcpdump could not be started. Missing sudo permissions?"
        exit 1
    fi
    exit 0
fi

if [ -z "$filter" ]; then
    echo "No interface filter (-f) supplied. This provider requires container veth interfaces to be resolved before starting." >&2
    exit 1
fi

# $filter is intentionally unquoted: it is a pre-validated, space-separated BPF expression
# ("ifname vethXXXXXXX or ifname vethYYYYYYY or ...") and must be split into separate tcpdump argv tokens.
tcpdump -tt --micro -nn -v -i any $filter
