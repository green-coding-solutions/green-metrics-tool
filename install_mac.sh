#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
NC='\033[0m' # No Color

function print_message {
    echo ""
    echo "$1"
}

function generate_random_password() {
    local length=$1
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$length"
    echo
}

db_pw=''
api_url=''
metrics_url=''

while getopts "p:a:m:" o; do
    case "$o" in
        p)
            db_pw=${OPTARG}
            ;;
        a)
            api_url=${OPTARG}
            ;;
        m)
            metrics_url=${OPTARG}
            ;;
    esac
done

if [[ -z $api_url ]] ; then
    read -p "Please enter the desired API endpoint URL: (default: http://api.green-coding.internal:9142): " api_url
    api_url=${api_url:-"http://api.green-coding.internal:9142"}
fi

if [[ -z $metrics_url ]] ; then
    read -p "Please enter the desired metrics dashboard URL: (default: http://metrics.green-coding.internal:9142): " metrics_url
    metrics_url=${metrics_url:-"http://metrics.green-coding.internal:9142"}
fi

if [[ -f config.yml ]]; then
    password_from_file=$(awk '/postgresql:/ {flag=1; next} flag && /password:/ {print $2; exit}' config.yml)
fi

default_password=${password_from_file:-$(generate_random_password 12)}

if [[ -z "$db_pw" ]] ; then
    read -sp "Please enter the new password to be set for the PostgreSQL DB (default: $default_password): " db_pw
    echo "" # force a newline, because read -sp will consume it
    db_pw=${db_pw:-"$default_password"}
fi

print_message "Clearing old api.conf and frontend.conf files"
rm -Rf docker/nginx/api.conf
rm -Rf docker/nginx/frontend.conf

print_message "Updating compose.yml with current path ..."
cp docker/compose.yml.example docker/compose.yml
sed -i '' -e "s|PATH_TO_GREEN_METRICS_TOOL_REPO|$PWD|" docker/compose.yml
sed -i '' -e "s|PLEASE_CHANGE_THIS|$db_pw|" docker/compose.yml

print_message "Updating config.yml with new password ..."
cp config.yml.example config.yml
sed -i '' -e "s|PLEASE_CHANGE_THIS|$db_pw|" config.yml

print_message "Updating project with provided URLs ..."
sed -i '' -e "s|__API_URL__|$api_url|" config.yml
sed -i '' -e "s|__METRICS_URL__|$metrics_url|" config.yml
cp docker/nginx/api.conf.example docker/nginx/api.conf
host_api_url=`echo $api_url | sed -E 's/^\s*.*:\/\///g'`
host_api_url=${host_api_url%:*}
sed -i '' -e "s|__API_URL__|$host_api_url|" docker/nginx/api.conf
cp docker/nginx/frontend.conf.example docker/nginx/frontend.conf
host_metrics_url=`echo $metrics_url | sed -E 's/^\s*.*:\/\///g'`
host_metrics_url=${host_metrics_url%:*}
sed -i '' -e "s|__METRICS_URL__|$host_metrics_url|" docker/nginx/frontend.conf
cp frontend/js/helpers/config.js.example frontend/js/helpers/config.js
sed -i '' -e "s|__API_URL__|$api_url|" frontend/js/helpers/config.js
sed -i '' -e "s|__METRICS_URL__|$metrics_url|" frontend/js/helpers/config.js

print_message "Checking out further git submodules ..."
git submodule update --init

print_message "Setting up python venv"
python3 -m venv venv
source venv/bin/activate

print_message "Setting GMT in include path for python via .pth file"
find venv -type d -name "site-packages" -exec sh -c 'echo $PWD > "$0/gmt-lib.pth"' {} \;

print_message "Adding hardware_info_root.py to sudoers file"
PYTHON_PATH=$(which python3)
PWD=$(pwd)
echo "ALL ALL=(ALL) NOPASSWD:$PYTHON_PATH $PWD/lib/hardware_info_root.py" | sudo tee /etc/sudoers.d/green_coding_hardware_info

print_message "Setting the hardare hardware_info to be owned by root"
sudo cp -f $PWD/lib/hardware_info_root_original.py $PWD/lib/hardware_info_root.py
sudo chown root: $PWD/lib/hardware_info_root.py
sudo chmod 755 $PWD/lib/hardware_info_root.py

print_message "Adding powermetrics to sudoers file"
echo "ALL ALL=(ALL) NOPASSWD:/usr/bin/powermetrics" | sudo tee /etc/sudoers.d/green_coding_powermetrics
echo "ALL ALL=(ALL) NOPASSWD:/usr/bin/killall powermetrics" | sudo tee /etc/sudoers.d/green_coding_kill_powermetrics
echo "ALL ALL=(ALL) NOPASSWD:/usr/bin/killall -9 powermetrics" | sudo tee /etc/sudoers.d/green_coding_kill_powermetrics_sigkill

print_message "Writing to /etc/hosts file..."
etc_hosts_line_1="127.0.0.1 green-coding-postgres-container"
etc_hosts_line_2="127.0.0.1 ${host_api_url} ${host_metrics_url}"

# Entry 1 is needed for the local resolution of the containers through the jobs.py and runner.py
if ! sudo grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
    echo -e "\n$etc_hosts_line_1" | sudo tee -a /etc/hosts
else
    echo "Entry was already present..."
fi

# Entry 2 can be external URLs. These should not resolve to localhost if not explcitely wanted
if [[ ${host_metrics_url} == *".green-coding.internal"* ]];then
    if ! sudo grep -Fxq "$etc_hosts_line_2" /etc/hosts; then
        echo -e "\n$etc_hosts_line_2" | sudo tee -a /etc/hosts
    else
        echo "Entry was already present..."
    fi
fi

if ! command -v stdbuf &> /dev/null; then
    print_message "Trying to install 'coreutils' via homebew. If this fails (because you do not have brew or use another package manager), please install it manually ..."
    brew install coreutils
fi

print_message "Building binaries ..."
metrics_subdir="metric_providers"
parent_dir="./$metrics_subdir"
make_file="Makefile"
find "$parent_dir" -type d |
while IFS= read -r subdir; do
    make_path="$subdir/$make_file"
    if [[ -f "$make_path" ]] && [[ "$make_path" == *"/mach/"* ]]; then
        echo "Installing $subdir/metric-provider-binary ..."
        rm -f $subdir/metric-provider-binary 2> /dev/null
        make -C $subdir
    fi
done

print_message "Building / Updating docker containers"
docker compose -f docker/compose.yml down
docker compose -f docker/compose.yml build
docker compose -f docker/compose.yml pull

print_message "Updating python requirements"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m pip install -r metric_providers/psu/energy/ac/xgboost/machine/model/requirements.txt


echo ""
echo -e "${GREEN}Successfully installed Green Metrics Tool!${NC}"
echo -e "Please remember to always activate your venv when using the GMT with 'source venv/bin/activate'"
