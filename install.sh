#!/bin/bash
set -euo pipefail

read -sp "Please enter the new password to be set for the PostgreSQL DB: " db_pw

echo "Updating compose.yml with current path ..."
cp docker/compose.yml.example docker/compose.yml
sed -i -e "s|PATH_TO_GREEN_METRICS_TOOL_REPO|$PWD|" docker/compose.yml
sed -i -e "s|PLEASE_CHANGE_THIS|$db_pw|" docker/compose.yml

echo "Updating config.yml with new password ..."
cp config.yml.example config.yml
sed -i -e "s|PLEASE_CHANGE_THIS|$db_pw|" config.yml


echo "Building binaries ..."
metrics_subdir="tools/metric-providers"
parent_dir="./$metrics_subdir"
make_file="Makefile"
find "$parent_dir" -type d |
while IFS= read -r subdir; do
    make_path="$subdir/$make_file"
    if [[ -f "$make_path" ]]; then
        echo "Installing $subdir/static-binary ..."
        rm -f $subdir/static-binary 2> /dev/null
        make -C $subdir
        chmod +x $subdir/static-binary
    fi
done

sudo_line="$USER ALL=(ALL) NOPASSWD: $PWD/tools/metric-providers/rapl/system/MSR/static-binary -i 1000"
sudo_line_2="$USER ALL=(ALL) NOPASSWD: $PWD/tools/metric-providers/rapl/system/MSR/static-binary -i 100"
etc_hosts_line_1="127.0.0.1 green-coding-postgres-container"
etc_hosts_line_2="127.0.0.1 api.green-coding.local metrics.green-coding.local"

echo "Writing to /etc/sudoers file..."
if ! sudo grep -Fxq "$sudo_line" /etc/sudoers; then
    echo $sudo_line | sudo tee -a /etc/sudoers
else
    echo "Entry was already present..."
fi


if ! sudo grep -Fxq "$sudo_line_2" /etc/sudoers; then
    echo $sudo_line_2 | sudo tee -a /etc/sudoers
else    
    echo "Entry was already present..."
fi

echo "Writing to /etc/hosts file..."
if ! sudo grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
    echo $etc_hosts_line_1 | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi

if ! sudo grep -Fxq "$etc_hosts_line_2" /etc/hosts; then
    echo $etc_hosts_line_2 | sudo tee -a /etc/hosts
else    
    echo "Entry was already present..."
fi
