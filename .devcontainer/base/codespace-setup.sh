#!/bin/bash
set -euo pipefail

sudo apt update && \
sudo apt install -y curl git make gcc python3 python3-pip python3-venv

# we have to rename this makefile as it doesn't compile in Codespaces
if [ -f /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile ]; then
    mv /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile.bak
fi

/workspaces/green-metrics-tool/install_linux.sh -p testpw -a "https://${CODESPACE_NAME}-9142.app.github.dev" -m "https://${CODESPACE_NAME}-9143.app.github.dev" -t -i -s
source venv/bin/activate

# Also add XGBoost, as we need it
python3 -m pip install -r /workspaces/green-metrics-tool/metric_providers/psu/energy/ac/xgboost/machine/model/requirements.txt

# make edits to ports so we can use 9143 to access front end
sed -i 's/listen \[::\]:9142;/listen [::]:9143;/; s/listen 9142;/listen 9143;/' /workspaces/green-metrics-tool/docker/nginx/frontend.conf
sed -i '/green-coding-nginx:/,/green-coding-gunicorn:/ s/\(- 9142:80\)/- 9142:9142\n      - 9143:9143/' /workspaces/green-metrics-tool/docker/compose.yml

python3 /workspaces/green-metrics-tool/disable_metric_providers.py --categories RAPL Machine Sensors Debug --providers NetworkIoCgroupContainerProvider NetworkConnectionsProxyContainerProvider PsuEnergyAcSdiaMachineProvider

git clone https://github.com/green-coding-berlin/example-applications.git /workspaces/examples

source venv/bin/activate

docker compose -f /workspaces/green-metrics-tool/docker/compose.yml up -d

gh codespace ports visibility 9142:public -c $CODESPACE_NAME

gh codespace ports visibility 9143:public -c $CODESPACE_NAME