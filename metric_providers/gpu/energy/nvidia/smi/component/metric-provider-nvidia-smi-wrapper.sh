#!/bin/bash
set -euo pipefail

i='100'

while getopts "i:" o; do
    case "$o" in
        i)
            i=${OPTARG}
            ;;
    esac
done

i=$(bc <<< "scale=3; $i / 1000")

while true; do
    echo -en $(date +"%s%6N") $(nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits| awk '{ gsub("\\.", ""); print }')"0\n"
    sleep $i
done
