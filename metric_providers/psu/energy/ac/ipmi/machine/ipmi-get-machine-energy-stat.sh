#! /bin/bash
set -euo pipefail

i=''

while getopts "i:" o; do
    case "$o" in
        i)
            i=${OPTARG}
            ;;
    esac
done

while true; do
    echo -en $(($(date +%s%N)/1000)) $(sudo /usr/sbin/ipmi-dcmi --get-system-power-statistics | head -1 |  awk '{print $4}')"\n"
    sleep ${i:-0.1}

done
