#!/bin/bash
set -euo pipefail

sudo apt update && \
sudo apt upgrade -y && \
sudo apt install -y curl git make gcc python3 python3-pip python3-venv

# we have to rename this makefile as it doesn't compile in Codespaces
if [ -f /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile ]; then
    mv /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile.bak
fi

/workspaces/green-metrics-tool/install_linux.sh -p testpw -a "https://${CODESPACE_NAME}-9142.app.github.dev" -m "https://${CODESPACE_NAME}-9142.app.github.dev" -tsed -i 's/listen \[::\]:9142;/listen [::]:9143;/; s/listen 9142;/listen 9143;/' /somewhere/file.conf

sed -i 's/listen \[::\]:9142;/listen [::]:9143;/; s/listen 9142;/listen 9143;/' /workspaces/green-metrics-tool/docker/nginx/frontend.conf
sed -i '/green-coding-nginx:/,/green-coding-gunicorn:/ s/\(- 9142:80\)/- 9142:9142\n      - 9143:9143/' /workspaces/green-metrics-tool/docker/compose.yml
