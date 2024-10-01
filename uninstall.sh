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
docker rmi postgres:15
docker rmi docker-test-green-coding-gunicorn
docker rmi docker-green-coding-gunicorn
docker system prune

if [[ $(uname) == "Linux" ]]; then
    if lsb_release -is | grep -q "Fedora"; then
        sudo dnf -y install msr-tools lm_sensors lm_sensors-devel glib2 glib2-devel tinyproxy stress-ng lshw ipmitool
    else
        sudo apt remove lm-sensors libsensors-dev libglib2.0-0 libglib2.0-dev tinyproxy stress-ng lshw freeipmi-tools ipmitool msr-tools -y
    fi
fi

