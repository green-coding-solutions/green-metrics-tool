#!/usr/bin/env bash
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

if [[ $activate_scenario_runner == true ]] ; then
    print_message "Installing needed binaries for building ..."
    if cat /etc/os-release | grep -q "Fedora"; then
        sudo dnf -y install glib2 glib2-devel tinyproxy stress-ng lshw libcurl-devel
    elif cat /etc/os-release | grep -q "openSUSE"; then
        sudo zypper -n in glib2-tools glib2-devel tinyproxy stress-ng lshw libcurl-devel
    else
        sudo apt-get update
        sudo apt-get install -y  libglib2.0-0 libglib2.0-dev tinyproxy stress-ng lshw libcurl4-openssl-dev
    fi

    if cat /etc/os-release | grep -q "Fedora"; then
        if ! sudo dnf -y install lm_sensors lm_sensors-devel; then
            print_message "Failed to install lm_sensors lm_sensors-devel;" >&2
            print_message "You can add -S to the install script to skip installing lm_sensors. However cluster mode and temperature reporters will not work then." >&2
            exit 1
        fi
    elif cat /etc/os-release | grep -q "openSUSE"; then
        if ! sudo zypper -n in sensors libsensors4-devel; then
            print_message "Failed to install sensors libsensors4-devel; continuing without Sensors."
        fi
    else
        if ! sudo apt-get install -y lm-sensors libsensors-dev; then
           print_message "Failed to install lm-sensors libsensors-dev;" >&2
            print_message "You can add -S to the install script to skip installing lm_sensors. However cluster mode and temperature reporters will not work then." >&2
           exit 1
        fi
    fi

    sudo systemctl stop tinyproxy
    sudo systemctl disable tinyproxy

    if [[ $install_nvidia_toolkit_headers == true ]] ; then
        print_message "Installing nvidia toolkit headers"
        if cat /etc/os-release | grep -q "Fedora"; then
            curl -O https://developer.download.nvidia.com/compute/cuda/repos/fedora$(rpm -E %fedora)/x86_64/cuda-fedora$(rpm -E %fedora).repo
            sudo mv cuda-fedora$(rpm -E %fedora).repo /etc/yum.repos.d/
            sudo dnf makecache
            if ! sudo dnf -y install libnvidia-ml cuda-nvml-devel-12-9; then
                print_message "Failed to install nvidia toolkit headers; Please remove --nvidia-gpu flag and install manually" >&2
                exit 1
            else
                sudo ln -s /usr/lib64/libnvidia-ml.so.1 /usr/lib64/libnvidia-ml.so
            fi
        else
            if ! sudo apt-get install -y libnvidia-ml-dev; then
                print_message "Failed to install nvidia toolkit headers; Please remove --nvidia-gpu flag and install manually" >&2
                exit 1
            fi
        fi
    fi

    print_message "Building C libs"
    make -C "lib/c"

    build_binaries


    if [[ $build_sgx == true ]] ; then
        print_message "Building sgx binaries"
        make -C lib/sgx-software-enable
        mv lib/sgx-software-enable/sgx_enable tools/
        rm lib/sgx-software-enable/sgx_enable.o
    fi

    print_message "Enabling cache cleanup without sudo via sudoers entry"
    sysctl_path=$(realpath "/usr/sbin/sysctl")
    check_file_permissions "$sysctl_path"
    echo "${USER} ALL=(ALL) NOPASSWD:${sysctl_path} -w vm.drop_caches=3" | sudo tee /etc/sudoers.d/green-coding-drop-caches
    sudo chmod 500 /etc/sudoers.d/green-coding-drop-caches

    print_message "Setting the cluster maintenance.py file to be owned by root"
    check_file_permissions $(realpath "/usr/bin/python3") # since it will be called later with this interpreter, we need to check if that is ok
    # we do not expose this sudoers entry here as it is only for cluster mode. Thus we want to reduce possible attack surface in case of bugs
    sudo cp -f "${PWD}/tools/cluster/maintenance_original.py" "${gmt_root_bin_dir}/maintenance.py"
    # using chown with UID:GID as names could be remapped and 0 is safe and also cross-platform (wheel in macos)
    sudo chown 0:0 "${gmt_root_bin_dir}/maintenance.py"
    sudo chmod 755 "${gmt_root_bin_dir}/maintenance.py"
    # delete old unsafe file from GMT v2.5
    sudo rm -f "${PWD}/tools/cluster/maintenance.py"

    if [[ $install_msr_tools == true ]] ; then
        print_message "Installing msr-tools"
        print_message "Important: If this step fails it means msr-tools is not available on you system"
        print_message ""
        if cat /etc/os-release | grep -q "Fedora"; then
            if ! sudo dnf -y install msr-tools; then
                print_message "Failed to install msr-tools; If you do not plan to use RAPL you can skip the installation by appending '-r'" >&2
                exit 1
            fi
        elif cat /etc/os-release | grep -q "openSUSE"; then
            if ! sudo zypper -n in msr-tools; then
                print_message "Failed to install msr-tools; continuing without RAPL."
            fi
        else
            if ! sudo apt-get install -y msr-tools; then
                print_message "Failed to install msr-tools; If you do not plan to use RAPL you can skip the installation by appending '-r'" >&2
                exit 1
            fi
        fi
    fi

    if [[ $install_ipmi == true ]] ; then
        print_message "Installing IPMI tools"
        print_message "Important: If this step fails it means ipmitool is not available on you system"
        {
            if cat /etc/os-release | grep -q "Fedora"; then
                sudo dnf -y install freeipmi ipmitool
            elif cat /etc/os-release | grep -q "openSUSE"; then
                sudo zypper -n in freeipmi ipmitool
            else
                sudo apt-get install -y freeipmi-tools ipmitool
            fi
            print_message "Adding IPMI to sudoers file"
            ipmi_dcmi_path=$(realpath "/usr/sbin/ipmi-dcmi")
            check_file_permissions "$ipmi_dcmi_path"
            echo "${USER} ALL=(ALL) NOPASSWD:${ipmi_dcmi_path} --get-system-power-statistics" | sudo tee /etc/sudoers.d/green-coding-ipmi-get-machine-energy-stat
            sudo chmod 500 /etc/sudoers.d/green-coding-ipmi-get-machine-energy-stat
            # remove old file name
            sudo rm -f /etc/sudoers.d/ipmi_get_machine_energy_stat
        } || {
            print_message "Failed to install and configure IPMI tools. Please try to install manually ..." >&2
            print_message "If you do not plan to use IPMI you can skip the installation by appending '-i'" >&2
            exit 1
        }

    fi
fi

if ! findmnt -n -o FSTYPE /tmp | grep tmpfs && [[ $ask_tmpfs == true ]]; then
    read -p "We strongly recommend mounting /tmp on a tmpfs. Do you want to do that? (y/N)" tmpfs
    if [[ "$tmpfs" == "Y" || "$tmpfs" == "y" ]] ; then
        if cat /etc/os-release | grep -q "Fedora"; then
            sudo systemctl unmask --now tmp.mount
        elif cat /etc/os-release | grep -q "openSUSE"; then
            print_message "Please mount /tmp manually as tmpfs. GMT cannot handle this in the install script" >&2
            exit 1
        else
            sudo systemctl enable /usr/share/systemd/tmp.mount
        fi
        reboot_echo_flag=true
    fi
fi

finalize
