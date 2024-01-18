#! /bin/bash
set -euo pipefail

cores=$(cat /proc/cpuinfo | grep processor | awk '{print $3}')

i=''

while getopts "i:" o; do
    case "$o" in
        i)
            i=${OPTARG}
            ;;
    esac
done

while true; do
    for core in $cores; do
        echo -en $(($(date +%s%N)/1000)) $(cat /sys/devices/system/cpu/cpu${core}/cpufreq/scaling_cur_freq) "${core}\n"
    done
    sleep ${i:-0.1}
done
