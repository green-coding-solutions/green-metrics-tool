#!/bin/bash

# example usage:> ./disable-metric-privoders.sh RAPL cgroup ac dc

echo "Editing config.yml... "

# First turn on all metric providers
echo "first turning on all metric providers"
sed -i "/metric-providers:/,/admin:/s/^#    /    /" test-config.yml

# Then comment out instances of the word
for word in "$@"
do
    echo "disabling metric providers containing $word ..."
   sed -i "/metric-providers:/,/admin:/s/^.*\.$word\./#&/g" test-config.yml
done

echo "fin"

