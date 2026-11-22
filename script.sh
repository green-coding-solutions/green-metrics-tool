#!/usr/bin/env bash

# Embodied carbon is calculated the same way as in Eco CI (scripts/misc.sh::get_embodied_co2):
#   embodied_g = SCI_M * (duration_s / SCI_USAGE_DURATION)
# SCI_M:              manufacturing carbon of the machine share in gCO2e (e.g. from https://datavizta.boavizta.org/serversimpact)
# SCI_USAGE_DURATION: expected lifetime in seconds. Default 4 years = 60*60*24*365*4
: "${SCI_M:?Please set SCI_M to the embodied carbon of the Hetzner CAX21 share in gCO2e}"
SCI_USAGE_DURATION=${SCI_USAGE_DURATION:-126144000}

while true; do

    # Clear tmp file
    echo -n > /tmp/machine_power.log

    source "$(dirname "$0")/hetzner_CAX21.sh"

    bash "$(dirname "$0")/cpu-utilization.sh" 60 > /tmp/machine_cpu_utilization.log

    while read -r read_var_time read_var_util; do
        echo "$read_var_time ${cloud_energy_hashmap[$read_var_util]}" | awk '{printf "%.9f\n", $1 * $2}' >> /tmp/machine_power.log
    done < /tmp/machine_cpu_utilization.log

    echo "On we go"

    # Since we poll every 1s Watts = Joules
    energy=$(awk '{s+=$1} END {print s}' /tmp/machine_power.log)
    energy=$(echo "scale=0; ($energy * 1000000) / 1" | bc) # microjoules

    # The measured duration is the sum of all sample intervals, so the embodied carbon matches the energy timeframe
    duration_s=$(awk '{s+=$1} END {printf "%.9f", s}' /tmp/machine_cpu_utilization.log)
    embodied_carbon_ug=$(echo "$SCI_M $duration_s $SCI_USAGE_DURATION" | awk '{printf "%.0f", $1 * ($2 / $3) * 1000000}') # g -> ug

    # timestamp in microseconds
    timestamp=$(date +%s%N | cut -b1-16)

    json_data=$(cat <<EOF
{
    "type": "machine.server",
    "machine": "Hetzner-CAX21",
    "project": "GMT-HOSTED-SERVICE",
    "tags": ["metrics.green-coding.io"],
    "time": $timestamp,
    "energy_uj": $energy,
    "embodied_carbon_ug": $embodied_carbon_ug
}

EOF
)

    curl -X POST "https://api.green-coding.io/v3/carbondb/add" \
        -H "X-Authentication: ${API_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "$json_data"

done
