#!/bin/bash
set -euxo pipefail

# we have to rename this makefile as it doesn't compile in Codespaces
if [ -f /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile ]; then
    mv /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile.bak
    git update-index --assume-unchanged /workspaces/green-metrics-tool/metric_providers/lm_sensors/Makefile
fi

/workspaces/green-metrics-tool/install_linux.sh -p testpw -a "https://${CODESPACE_NAME}-9142.app.github.dev" -m "https://${CODESPACE_NAME}-9143.app.github.dev" -t -i -s -l
source venv/bin/activate

# Also add XGBoost, as we need it
python3 -m pip install -r /workspaces/green-metrics-tool/metric_providers/psu/energy/ac/xgboost/machine/model/requirements.txt

# make edits to ports so we can use 9143 to access front end
sed -i 's/listen \[::\]:9142;/listen [::]:9143;/; s/listen 9142;/listen 9143;/' /workspaces/green-metrics-tool/docker/nginx/frontend.conf
sed -i 's/- 9142:9142/- 9142:9142\n      - 9143:9143/' /workspaces/green-metrics-tool/docker/compose.yml
sed -i 's|- ./nginx/block.conf|#- ./nginx/block.conf|' /workspaces/green-metrics-tool/docker/compose.yml

# activate XGBoost provider with sane values for GitHub Codespaces
sed -i 's/common:/common:\n      psu.energy.ac.xgboost.machine.provider.PsuEnergyAcXgboostMachineProvider:\n        resolution: 99\n        CPUChips: 1\n        HW_CPUFreq: 2800\n        CPUCores: 32\n        CPUThreads: 64\n        TDP: 270\n        HW_MemAmountGB: 256\n        VHost_Ratio: 0.03125\n/' /workspaces/green-metrics-tool/config.yml


git clone https://github.com/green-coding-solutions/example-applications.git --depth=1 --single-branch /workspaces/green-metrics-tool/example-applications || true

source venv/bin/activate

docker compose -f /workspaces/green-metrics-tool/docker/compose.yml down

docker compose -f /workspaces/green-metrics-tool/docker/compose.yml up -d


gh codespace ports visibility 9142:public -c $CODESPACE_NAME

gh codespace ports visibility 9143:public -c $CODESPACE_NAME