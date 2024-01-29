#! /bin/bash
set -euo pipefail

i=''
check_system=false
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
    first_line=$(sudo /usr/sbin/ipmi-dcmi --get-system-power-statistics | head -1)
    if ! [[ "$first_line" =~ ^"Current Power" ]]; then
        echo "Unable to find 'Current Power' in the output of 'sudo /usr/sbin/ipmi-dcmi --get-system-power-statistics' command. Found $first_line instead">&2
        exit 1
    fi

    current_power_watts=$(echo $first_line |  awk '{print $4}')
    if [[ $current_power_watts -le 0 ]]; then
        echo "Current Power Watts is $current_power_watts, which is unexpected">&2
        exit 1
    fi
    
    exit 0
fi


while true; do
    echo -en $(($(date +%s%N)/1000)) $(sudo /usr/sbin/ipmi-dcmi --get-system-power-statistics | head -1 |  awk '{print $4}')"\n"
    sleep ${i:-0.1}

done
