#!/bin/bash
set -euo pipefail

echo "Please note that this script does not remove pre-requisites like gcc, docker, curl etc. as it does not want to alter the system state"

function uninstall_python() {
    python3 -m pip uninstall -y -r requirements.txt
    python3 -m pip uninstall -y -r requirements-dev.txt
    python3 -m pip uninstall -y -r docker/requirements.txt
    python3 -m pip uninstall -y -r metric_providers/psu/energy/ac/xgboost/machine/model/requirements.txt
}

source venv/bin/activate

uninstall_python

deactivate

uninstall_python

rm -fR .

docker rmi nginx
docker rmi docker-test-green-coding-gunicorn
docker rmi docker-green-coding-gunicorn

read -p "Do you also want to remove the database and your data? (y/N) : " remove_db
if [[  "$remove_db" == "Y" || "$remove_db" == "y" ]] ; then
    docker rmi postgres:15
    docker volume rm docker_green-coding-postgres-data
fi

docker system prune

echo 'Removing sudoers.d entries'
# autocomplete might not find files and thus throw an error. We want to capture that
sudo rm -f /etc/sudoers.d/green_coding* || true # legacy / macOS
sudo rm -f /etc/sudoers.d/green-coding* || true # Linux


if [[ $(uname) == "Linux" ]]; then
    if cat /etc/os-release | grep -q "Fedora"; then
        sudo dnf -y remove msr-tools lm_sensors lm_sensors-devel glib2 glib2-devel tinyproxy stress-ng lshw ipmitool
    elif cat /etc/os-release | grep -q "openSUSE"; then
        sudo zypper rm -n msr-tools sensors libsensors4-devel glib2-tools glib2-devel tinyproxy stress-ng lshw freeipmi ipmitool
    else
        sudo apt remove -y msr-tools lm-sensors libsensors-dev libglib2.0-0 libglib2.0-dev tinyproxy stress-ng lshw freeipmi-tools ipmitool
    fi

    read -p "Do you also want to remove pre-install requirements (curl git make gcc python3 python3-devel)? (y/N) : " pre_install
    if [[  "$pre_install" == "Y" || "$pre_install" == "y" ]] ; then
        if cat /etc/os-release | grep -q "Fedora"; then
            sudo dnf remove -y git make gcc python3 python3-devel curl
        elif cat /etc/os-release | grep -q "openSUSE"; then
            sudo zypper rm -n git make gcc python313 python313-pip python313-virtualenv curl
        else
            sudo apt remove -y git make gcc python3 python3-pip python3-venv curl
        fi
    fi

    read -p "Do you also want to remove pre-install requirements (docker)? (y/N) : " pre_docker
    if [[  "$pre_docker" == "Y" || "$pre_docker" == "y" ]] ; then
        if cat /etc/os-release | grep -q "Fedora"; then
            sudo dnf remove -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        elif cat /etc/os-release | grep -q "openSUSE"; then
            sudo zypper rm -n docker docker-compose docker-compose-switch
        else
            sudo apt remove -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
        fi
    fi
fi

