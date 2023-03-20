#!/bin/bash
set -euo pipefail

apt-get update
apt install -y make gcc python3 python3-pip libpq-dev uidmap
apt-get remove -y docker docker-engine docker.io containerd runc
apt-get install -y ca-certificates curl gnupg lsb-release

su - gc -c "git clone https://github.com/green-coding-berlin/green-metrics-tool ~/green-metrics-tool \
&& cd ~/green-metrics-tool \
&& git submodule update --init \
&& python3 -m pip install -r ~/green-metrics-tool/requirements.txt \
&& python3 -m pip install -r ~/green-metrics-tool/metric_providers/psu/energy/ac/xgboost/system/model/requirements.txt"

mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo \
"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
$(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update

apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl disable --now docker.service docker.socket
apt-get install -y docker-ce-rootless-extras dbus-user-session

shutdown -r now

#
# You need to reboot here. So relogin and copy paste the rest
#

systemctl disable --now docker.service docker.socket

su - gc -c "dockerd-rootless-setuptool.sh install"

cat <<EOT >> /home/gc/.bashrc
export XDG_RUNTIME_DIR=/home/gc/.docker/run
export PATH=/usr/bin:$PATH
export DOCKER_HOST=unix:///home/gc/.docker/run/docker.sock
EOT

su - gc -c 'systemctl --user enable docker; loginctl enable-linger $(whoami)'

apt install -y lm-sensors libsensors-dev libglib2.0-0 libglib2.0-dev
sensors-detect --auto

# You only need these commands if you are planning to use the PowerSpy2.
pip install pyserial==3.5
apt install -y bluez