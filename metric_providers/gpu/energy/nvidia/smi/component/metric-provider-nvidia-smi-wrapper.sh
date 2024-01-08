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

nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits -lms $i | awk '{ "date +%s%N" | getline timestamp; print timestamp " " $0 }'
