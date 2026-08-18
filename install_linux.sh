#!/usr/bin/env bash
set -euo pipefail

if [[ $(uname) != "Linux" ]]; then
  echo "Error: This script can only be run on Linux."
  exit 1
fi

# Refreshing repo metadata (apt/dnf update) must never hang indefinitely, so we cap it hard at 3 minutes.
# Installs are not capped overall, as they can legitimately take a while,
# but we still bound how long connecting to the repo may take.
repo_metadata_refresh_timeout_s=180
apt_connect_timeout_opts=(-o Acquire::http::ConnectTimeout=10 -o Acquire::https::ConnectTimeout=10)

# dnf's 'timeout' setting is applied per mirror connection attempt (like apt's ConnectTimeout),
# not to the overall download/install, so this is safe to use unconditionally.
dnf_connect_timeout_opts=(--setopt=timeout=10)

# zypper has no CLI flag for a connection-only timeout, so as a fallback we cap the whole
# invocation. Kept generous since it also covers the actual package install.
zypper_timeout_s=300

source lib/install_shared.sh # will parse opts immediately

prepare_config

checkout_submodules

setup_python

build_containers

if [[ $activate_scenario_runner == true ]] ; then
    print_message "Installing needed binaries for building ..."
    if cat /etc/os-release | grep -q "Fedora"; then
        sudo dnf "${dnf_connect_timeout_opts[@]}" -y install tinyproxy stress-ng lshw libcurl-devel
    elif cat /etc/os-release | grep -q "openSUSE"; then
        sudo timeout "$zypper_timeout_s" zypper -n in stress-ng lshw libcurl-devel
    else
        sudo timeout "$repo_metadata_refresh_timeout_s" apt-get update
        sudo apt-get "${apt_connect_timeout_opts[@]}" install -y  libglib2.0-0 libglib2.0-dev tinyproxy stress-ng lshw libcurl4-openssl-dev
    fi

    if [[ $install_tinyproxy == true ]] ; then
        if cat /etc/os-release | grep -q "Fedora"; then
            sudo dnf "${dnf_connect_timeout_opts[@]}" -y install tinyproxy
        elif cat /etc/os-release | grep -q "openSUSE"; then
            sudo timeout "$zypper_timeout_s" zypper -n in tinyproxy
        else
            sudo timeout "$repo_metadata_refresh_timeout_s" apt-get update
            sudo apt-get "${apt_connect_timeout_opts[@]}" install -y tinyproxy
        fi
        sudo systemctl stop tinyproxy
        sudo systemctl disable tinyproxy
    fi





    if [[ $install_sensors == true ]] ; then
        if cat /etc/os-release | grep -q "Fedora"; then
            if ! sudo dnf "${dnf_connect_timeout_opts[@]}" -y install glib2 glib2-devel lm_sensors lm_sensors-devel; then
                print_message "Failed to install lm_sensors lm_sensors-devel;" >&2
                print_message "You can add -S to the install script to skip installing lm_sensors. However cluster mode and temperature reporters will not work then." >&2
                exit 1
            fi
        elif cat /etc/os-release | grep -q "openSUSE"; then
            if ! sudo timeout "$zypper_timeout_s" zypper -n in glib2-tools glib2-devel sensors libsensors4-devel; then
                print_message "Failed to install sensors libsensors4-devel; continuing without Sensors."
            fi
        else
            if ! sudo apt-get "${apt_connect_timeout_opts[@]}" install -y lm-sensors libsensors-dev; then
                print_message "Failed to install libglib2.0-0 libglib2.0-dev lm-sensors libsensors-dev;" >&2
                print_message "You can add -S to the install script to skip installing lm_sensors. However cluster mode and temperature reporters will not work then." >&2
               exit 1
            fi
        fi
    fi

    if [[ $install_nvidia_toolkit_headers == true ]] ; then
        print_message "Installing nvidia toolkit headers"
        if cat /etc/os-release | grep -q "Fedora"; then
            curl --connect-timeout 10 -O https://developer.download.nvidia.com/compute/cuda/repos/fedora$(rpm -E %fedora)/x86_64/cuda-fedora$(rpm -E %fedora).repo
            sudo mv cuda-fedora$(rpm -E %fedora).repo /etc/yum.repos.d/
            sudo timeout "$repo_metadata_refresh_timeout_s" dnf "${dnf_connect_timeout_opts[@]}" makecache
            if ! sudo dnf "${dnf_connect_timeout_opts[@]}" -y install libnvidia-ml cuda-nvml-devel-12-9; then
                print_message "Failed to install nvidia toolkit headers; Please remove --nvidia-gpu flag and install manually" >&2
                exit 1
            else
                sudo ln -s /usr/lib64/libnvidia-ml.so.1 /usr/lib64/libnvidia-ml.so
            fi
        else
            if ! sudo apt-get "${apt_connect_timeout_opts[@]}" install -y libnvidia-ml-dev; then
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
    sudo chmod 400 /etc/sudoers.d/green-coding-drop-caches

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
            if ! sudo dnf "${dnf_connect_timeout_opts[@]}" -y install msr-tools; then
                print_message "Failed to install msr-tools; If you do not plan to use RAPL you can skip the installation by appending '-R'" >&2
                exit 1
            fi
        elif cat /etc/os-release | grep -q "openSUSE"; then
            if ! sudo timeout "$zypper_timeout_s" zypper -n in msr-tools; then
                print_message "Failed to install msr-tools; continuing without RAPL."
            fi
        else
            if ! sudo apt-get "${apt_connect_timeout_opts[@]}" install -y msr-tools; then
                print_message "Failed to install msr-tools; If you do not plan to use RAPL you can skip the installation by appending '-R'" >&2
                exit 1
            fi
        fi
    fi

    if [[ $install_ipmi == true ]] ; then
        print_message "Installing IPMI tools"
        print_message "Important: If this step fails it means ipmitool is not available on you system"
        {
            if cat /etc/os-release | grep -q "Fedora"; then
                sudo dnf "${dnf_connect_timeout_opts[@]}" -y install freeipmi ipmitool
            elif cat /etc/os-release | grep -q "openSUSE"; then
                sudo timeout "$zypper_timeout_s" zypper -n in freeipmi ipmitool
            else
                sudo apt-get "${apt_connect_timeout_opts[@]}" install -y freeipmi-tools ipmitool
            fi
            print_message "Adding IPMI to sudoers file"
            ipmi_dcmi_path=$(realpath "/usr/sbin/ipmi-dcmi")
            check_file_permissions "$ipmi_dcmi_path"
            echo "${USER} ALL=(ALL) NOPASSWD:${ipmi_dcmi_path} --get-system-power-statistics" | sudo tee /etc/sudoers.d/green-coding-ipmi-get-machine-energy-stat
            sudo chmod 400 /etc/sudoers.d/green-coding-ipmi-get-machine-energy-stat
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
