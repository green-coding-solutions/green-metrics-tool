#!/bin/bash

# example usage:> ./disable-metric-privoders.sh RAPL cgroup ac dc

config="config.yml"
echo "Editing ${config}... "

# First turn on all metric providers
echo "first turning on all metric providers"
sed -i "/metric-providers:/,/admin:/s/^#    /    /" $config

# Then disable specific providers
for word in "$@"
do
    echo "disabling metric providers containing $word ..."
    if [[ "$word" == "xgboost" ]]; then
        sed -i "/\.${word}\./,+7s/^/#/" $config
    else
        sed -i "/\.${word}\./,+1s/^/#/" $config
    fi 
done

echo "fin"

