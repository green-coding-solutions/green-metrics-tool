#! /bin/bash
set -euo pipefail

cores=$(cat /proc/cpuinfo | grep processor | awk '{print $3}')
check_system=false
i=''

while getopts "i:c" o; do
    case "$o" in
        i)
            i=${OPTARG}
            ;;
        c)
            check_system=true
            ;;
    esac
done

if $check_system; then
    file_path="/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"

    if [ -e "$file_path" ]; then
        if ! output=$(cat "$file_path" 2>&1); then
            if [[ "$output" == *"Permission denied"* ]]; then
                echo "Cannot read $file_path.">&2
                exit 1
            fi
        fi
    else
        echo "Could not find $file_path.">&2
        exit 1
    fi
    exit 0
fi

while true; do
    for core in $cores; do
        echo -en $(($(date +%s%N)/1000)) $(cat /sys/devices/system/cpu/cpu${core}/cpufreq/scaling_cur_freq) "${core}\n"
    done
    sleep ${i:-0.1}
done
