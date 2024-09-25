#! /bin/bash
set -euo pipefail

i='100'
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

i=$(bc <<< "scale=3; $i / 1000")

if $check_system; then
    first_line=$(sudo /usr/sbin/ipmi-dcmi --get-system-power-statistics | sed -n 1p)
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
    echo -en $(($(date +%s%N)/1000)) $(sudo /usr/sbin/ipmi-dcmi --get-system-power-statistics | head -1 |  awk '{print $4}')"000\n"
    sleep $i
done
