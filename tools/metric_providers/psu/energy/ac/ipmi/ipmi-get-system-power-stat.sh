#! /bin/bash
while true; do
    echo -n $(($(date +%s%N)/1000)) "" && sudo /usr/sbin/ipmi-dcmi --get-system-power-statistics | head -1 |  awk '{print $4}'
    sleep ${2:-0.1}

done
