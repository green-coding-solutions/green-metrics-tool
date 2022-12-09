#!/bin/bash

# example usage:> ./disable-metric-privoders.sh RAPL Always-Off
# See config.yml.example for category names
config="config.yml"
echo "Editing ${config}... "

# First turn on all metric providers
echo "first turning on all metric providers"
sed -i "/metric-providers:/,/admin:/   s/^#    /    /" $config

# Then disable specific providers
for category in "$@"
do
    echo "disabling metric providers in category $category ..."
    #  /#--- ${category}/,/#---/          -> Range to disable between
    #  { /#--- ${category}/b; /#---/b;    -> Make the range exclusive (default is inclusive)
    #  s/^/#/                             -> Substitution to make between the range
    sed -i -e"/#--- ${category}/,/#---/   { /#--- ${category}/b; /#---/b; s/^/#/ }" $config
done

echo "fin"
