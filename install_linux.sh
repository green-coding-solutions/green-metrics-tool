#!/bin/bash
set -euo pipefail

function print_message {
    echo ""
    echo "$1"
}

db_pw=''
while getopts "p:" o; do
    case "$o" in
        p)
            db_pw=${OPTARG}
            ;;
    esac
done

if [[ -z "$db_pw" ]] ; then
    read -sp "Please enter the new password to be set for the PostgreSQL DB: " db_pw
fi

print_message "Updating compose.yml with current path ..."
cp docker/compose.yml.example docker/compose.yml
sed -i -e "s|PATH_TO_GREEN_METRICS_TOOL_REPO|$PWD|" docker/compose.yml
sed -i -e "s|PLEASE_CHANGE_THIS|$db_pw|" docker/compose.yml

print_message "Updating config.yml with new password ..."
cp config.yml.example config.yml
sed -i -e "s|PLEASE_CHANGE_THIS|$db_pw|" config.yml

print_message "Installing needed binaries for building ..."
if lsb_release -is | grep -q "Fedora"; then
    sudo dnf -y install lm_sensors lm_sensors-devel glib2 glib2-devel
else
    sudo apt install -y lm-sensors libsensors-dev libglib2.0-0 libglib2.0-dev
fi

print_message "Building binaries ..."
metrics_subdir="metric_providers"
parent_dir="./$metrics_subdir"
make_file="Makefile"
find "$parent_dir" -type d |
while IFS= read -r subdir; do
    make_path="$subdir/$make_file"
    if [[ -f "$make_path" ]]; then
        echo "Installing $subdir/metric-provider-binary ..."
        rm -f $subdir/metric-provider-binary 2> /dev/null
        make -C $subdir
    fi
done

print_message "Building sgx binaries"
make -C lib/sgx-software-enable
mv lib/sgx-software-enable/sgx_enable tools/
rm lib/sgx-software-enable/sgx_enable.o

print_message "Adding hardware_info_root.py to sudoers file"
PYTHON_PATH=$(which python3)
PWD=$(pwd)
echo "ALL ALL=(ALL) NOPASSWD:$PYTHON_PATH $PWD/lib/hardware_info_root.py" | sudo tee /etc/sudoers.d/green_coding_hardware_info


etc_hosts_line_1="127.0.0.1 green-coding-postgres-container"
etc_hosts_line_2="127.0.0.1 api.green-coding.local metrics.green-coding.local"

print_message "Writing to /etc/hosts file..."
if ! sudo grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
    echo "$etc_hosts_line_1" | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi

if ! sudo grep -Fxq "$etc_hosts_line_2" /etc/hosts; then
    echo "$etc_hosts_line_2" | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi
