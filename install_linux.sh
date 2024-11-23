#!/bin/bash
set -euo pipefail

if [[ $(uname) != "Linux" ]]; then
  echo "Error: This script can only be run on Linux."
  exit 1
fi

source lib/install_shared.sh # will parse opts immediately

prepare_config

checkout_submodules

setup_python

build_containers


print_message "Installing needed binaries for building ..."
if lsb_release -is | grep -q "Fedora"; then
    sudo dnf -y install lm_sensors lm_sensors-devel glib2 glib2-devel tinyproxy stress-ng lshw
else
    sudo apt-get update
    sudo apt-get install -y lm-sensors libsensors-dev libglib2.0-0 libglib2.0-dev tinyproxy stress-ng lshw
fi
sudo systemctl stop tinyproxy
sudo systemctl disable tinyproxy

print_message "Building C libs"
make -C "lib/c"

build_binaries

if [[ $build_sgx == true ]] ; then
    print_message "Building sgx binaries"
    make -C lib/sgx-software-enable
    mv lib/sgx-software-enable/sgx_enable tools/
    rm lib/sgx-software-enable/sgx_enable.o
fi

print_message "Setting the cluster cleanup.sh file to be owned by root"
sudo cp -f $PWD/tools/cluster/cleanup_original.sh $PWD/tools/cluster/cleanup.sh
sudo chown root:root $PWD/tools/cluster/cleanup.sh
sudo chmod 755 $PWD/tools/cluster/cleanup.sh
sudo chmod +x $PWD/tools/cluster/cleanup.sh


if [[ $install_msr_tools == true ]] ; then
    print_message "Installing msr-tools"
    print_message "Important: If this step fails it means msr-tools is not available on you system"
    print_message "If you do not plan to use RAPL you can skip the installation by appending '-r'"
    if lsb_release -is | grep -q "Fedora"; then
        sudo dnf -y install msr-tools
    else
        sudo apt-get install -y msr-tools
    fi
fi

if [[ $install_ipmi == true ]] ; then
    print_message "Installing IPMI tools"
    print_message "Important: If this step fails it means ipmitool is not available on you system"
    print_message "If you do not plan to use IPMI you can skip the installation by appending '-i'"
    if lsb_release -is | grep -q "Fedora"; then
        sudo dnf -y install ipmitool
    else
        sudo apt-get install -y freeipmi-tools ipmitool
    fi
    print_message "Adding IPMI to sudoers file"
    check_file_permissions "/usr/sbin/ipmi-dcmi"
    echo "ALL ALL=(ALL) NOPASSWD:/usr/sbin/ipmi-dcmi --get-system-power-statistics" | sudo tee /etc/sudoers.d/green-coding-ipmi-get-machine-energy-stat
    sudo chmod 500 /etc/sudoers.d/green-coding-ipmi-get-machine-energy-stat
    # remove old file name
    sudo rm -f /etc/sudoers.d/ipmi_get_machine_energy_stat
fi

if ! mount | grep -E '\s/tmp\s' | grep -Eq '\stmpfs\s' && [[ $ask_tmpfs == true ]]; then
    read -p "We strongly recommend mounting /tmp on a tmpfs. Do you want to do that? (y/N)" tmpfs
    if [[ "$tmpfs" == "Y" || "$tmpfs" == "y" ]] ; then
        if lsb_release -is | grep -q "Fedora"; then
            sudo systemctl unmask --now tmp.mount
        else
            sudo systemctl enable /usr/share/systemd/tmp.mount
        fi
        reboot_echo_flag=true
    fi
fi

finalize
