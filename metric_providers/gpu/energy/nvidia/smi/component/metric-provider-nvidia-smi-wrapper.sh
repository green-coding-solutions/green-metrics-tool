#!/bin/bash
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
    echo -en $(($(date +%s%N)/1000)) $(nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits| awk '{ gsub("\\.", ""); print }')"\n"
    sleep ${i:-0.1}
done
