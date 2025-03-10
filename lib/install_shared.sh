#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
NC='\033[0m' # No Color

db_pw=''
api_url=''
metrics_url=''
build_docker_containers=true
install_python_packages=true
modify_hosts=true
ask_tmpfs=true
install_ipmi=true
install_sensors=true
build_sgx=true
install_msr_tools=true
# The system site packages are only an option to choose if you are in temporary VMs anyway
# Not recommended for classical developer system
use_system_site_packages=false
reboot_echo_flag=false
enable_ssl=true
ask_ssl=true
cert_key=''
cert_file=''
enterprise=false
ask_ping=true
force_send_ping=false

function print_message {
    echo ""
    echo "$1"
}

function generate_random_password() {
    local length=$1
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$length"
    echo
}

function check_file_permissions() {
    local file=$1

    # Check if the file exists
    if [ ! -e "$file" ]; then
        echo "File '$file' does not exist."
        return 1
    fi

    # Check if the file is owned by root
    if [[ $(uname) == "Darwin" ]]; then
        if [ "$(stat -f %Su "$file")" != "root" ]; then
            echo "File '$file' is not owned by root."
            return 1
        fi
    else
        if [ "$(stat -c %U "$file")" != "root" ]; then
            echo "File '$file' is not owned by root."
            return 1
        fi
    fi

        # Check if the file is owned by root

    # Check if the file permissions are read-only for group and others using regex

    if [[ $(uname) == "Darwin" ]]; then
        local permissions=$(stat -f %Sp "$file")
    else
        local permissions=$(stat -c %A "$file") # Linux
    fi

    if [ -L "$file" ]; then
        echo "File '$file' is a symbolic link. Following ..."
        check_file_permissions $(readlink -f $file)
        return $?
    elif [[ ! $permissions =~ ^-r..r-.r-.$ ]]; then
        echo "File '$file' is not read-only for group and others or not a regular file"
        return 1
    fi

    echo "File $file is save to create sudoers entry for"

    return 0
}


function prepare_config() {

    print_message "Clearing old api.conf and frontend.conf files"
    rm -Rf docker/nginx/api.conf
    rm -Rf docker/nginx/frontend.conf

    local sed_command="sed -i"
    if [[ $(uname) == "Darwin" ]]; then
        sed_command="sed -i ''"
    fi

    print_message "Updating compose.yml with current path ..."
    cp docker/compose.yml.example docker/compose.yml
    eval "${sed_command} -e \"s|PATH_TO_GREEN_METRICS_TOOL_REPO|$PWD|\" docker/compose.yml"
    eval "${sed_command} -e \"s|PLEASE_CHANGE_THIS|$db_pw|\" docker/compose.yml"

    print_message "Updating config.yml with new password ..."
    cp config.yml.example config.yml
    eval "${sed_command} -e \"s|PLEASE_CHANGE_THIS|$db_pw|\" config.yml"

    print_message "Updating project with provided URLs ..."

    eval "${sed_command} -e \"s|__API_URL__|$api_url|\" config.yml"
    eval "${sed_command} -e \"s|__METRICS_URL__|$metrics_url|\" config.yml"

    cp docker/nginx/api.conf.example docker/nginx/api.conf
    local host_api_url=`echo $api_url | sed -E 's/^\s*.*:\/\///g'`
    local host_api_url=${host_api_url%:*}
    eval "${sed_command} -e \"s|__API_URL__|$host_api_url|\" docker/nginx/api.conf"

    cp docker/nginx/block.conf.example docker/nginx/block.conf

    cp docker/nginx/frontend.conf.example docker/nginx/frontend.conf
    local host_metrics_url=`echo $metrics_url | sed -E 's/^\s*.*:\/\///g'`
    local host_metrics_url=${host_metrics_url%:*}
    eval "${sed_command} -e \"s|__METRICS_URL__|$host_metrics_url|\" docker/nginx/frontend.conf"

    cp frontend/js/helpers/config.js.example frontend/js/helpers/config.js
    eval "${sed_command} -e \"s|__API_URL__|$api_url|\" frontend/js/helpers/config.js"
    eval "${sed_command} -e \"s|__METRICS_URL__|$metrics_url|\" frontend/js/helpers/config.js"

    if [[ $enterprise == true ]]; then
        eval "${sed_command} -e \"s|__ACTIVATE_CARBON_DB__|true|\" frontend/js/helpers/config.js"
        eval "${sed_command} -e \"s|__ACTIVATE_POWER_HOG__|true|\" frontend/js/helpers/config.js"
        eval "${sed_command} -e \"s|#EE-ONLY#||\" docker/compose.yml"

        eval "${sed_command} -e \"s|ee_token:.*$|ee_token: ${ee_token}|\" config.yml"
    else
        eval "${sed_command} -e \"s|__ACTIVATE_CARBON_DB__|false|\" frontend/js/helpers/config.js"
        eval "${sed_command} -e \"s|__ACTIVATE_POWER_HOG__|false|\" frontend/js/helpers/config.js"
    fi

    if [[ $enable_ssl == true ]] ; then
        eval "${sed_command} -e \"s|9142:9142|443:443|\" docker/compose.yml"
        eval "${sed_command} -e \"s|9142:9142|443:443|\" docker/compose.yml"

        eval "${sed_command} -e \"s|#__SSL__||g\" docker/nginx/frontend.conf"
        eval "${sed_command} -e \"s|#__SSL__||g\" docker/nginx/api.conf"
        eval "${sed_command} -e \"s|#__SSL__||g\" docker/nginx/block.conf"

    else
        eval "${sed_command} -e \"s|#__DEFAULT__||g\" docker/nginx/frontend.conf"
        eval "${sed_command} -e \"s|#__DEFAULT__||g\" docker/nginx/api.conf"
        eval "${sed_command} -e \"s|#__DEFAULT__||g\" docker/nginx/block.conf"
    fi

    if [[ $modify_hosts == true ]] ; then

        local localhost_ip="127.0.0.1"
        local etc_hosts_line_1="green-coding-postgres-container"
        local etc_hosts_line_2="${host_api_url} ${host_metrics_url}"
        local etc_hosts_line_3="green-coding-redis-container"

        print_message "Checking /etc/hosts file..."

        # Entry 1 is needed for the local resolution of the containers through the jobs.py and runner.py
        if ! grep -Fq "$etc_hosts_line_1" /etc/hosts; then
            print_message "Writing $etc_hosts_line_1 to /etc/hosts file..."
            echo -e "\n$localhost_ip $etc_hosts_line_1" | sudo tee -a /etc/hosts
        fi

        if ! grep -Fq "$etc_hosts_line_3" /etc/hosts; then
            print_message "Writing $etc_hosts_line_3 to /etc/hosts file..."
            echo -e "\n$localhost_ip $etc_hosts_line_1" | sudo tee -a /etc/hosts
        fi


        # Entry 2 can be external URLs. These should not resolve to localhost if not explicitly wanted
        if [[ ${host_metrics_url} == *".green-coding.internal"* ]];then
            if ! grep -Fq "$etc_hosts_line_2" /etc/hosts; then
                print_message "Writing $etc_hosts_line_2 to /etc/hosts file..."
                echo "$localhost_ip $etc_hosts_line_2" | sudo tee -a /etc/hosts
            fi
        fi
    fi

}
function get_perms() {
    if [ "$(uname)" = "Darwin" ]; then
        stat -f "%A" "$1"
    else
        stat -c "%a" "$1"
    fi
}

function setup_python() {
    print_message "Setting up python venv"
    if [[ $use_system_site_packages == true ]] ; then
        python3 -m venv venv --system-site-packages
    else
        python3 -m venv venv
    fi
    source venv/bin/activate

    print_message "Setting GMT in include path for python via .pth file"
    find venv -type d -name "site-packages" -exec sh -c 'echo $PWD > "$0/gmt-lib.pth"' {} \;

    check_file_permissions "/usr/bin/python3"

    print_message "Adding python3 lib.hardware_info_root to sudoers file"
    # Please note the -m as here we will later call python3 without venv. It must understand the .lib imports
    # and not depend on venv installed packages
    local sudo_file="/etc/sudoers.d/green-coding-hardware-info"
    [ ! -f "$sudo_file" ] && sudo touch "$sudo_file"

    LINE1="${USER} ALL=(ALL) NOPASSWD:/usr/bin/python3 -m lib.hardware_info_root"
    LINE2="${USER} ALL=(ALL) NOPASSWD:/usr/bin/python3 -m lib.hardware_info_root --read-rapl-energy-filtering"

    grep -xF "$LINE1" "$sudo_file" || sudo echo "$LINE1" >> "$sudo_file"
    grep -xF "$LINE2" "$sudo_file" || sudo echo "$LINE2" >> "$sudo_file"

    current_perms=$(get_perms /etc/sudoers.d/green-coding-hardware-info 2>/dev/null || echo "000")
    if [ "$current_perms" != "544" ]; then
        sudo chmod 544 /etc/sudoers.d/green-coding-hardware-info
    fi



    # remove old file name
    [ -f /etc/sudoers.d/green_coding_hardware_info ] && sudo rm -f /etc/sudoers.d/green_coding_hardware_info

    if ! cmp -s "$PWD/lib/hardware_info_root_original.py" "$PWD/lib/hardware_info_root.py"; then
        print_message "Copying the hardware_info and setting it to be owned by root"
        sudo cp -f $PWD/lib/hardware_info_root_original.py $PWD/lib/hardware_info_root.py
        sudo chown root:$(id -gn root) $PWD/lib/hardware_info_root.py
        sudo chmod 755 $PWD/lib/hardware_info_root.py
    fi


    if [[ $install_python_packages == true ]] ; then
        print_message "Updating python requirements"
        python3 -m pip install --timeout 100 --retries 10 --upgrade pip
        python3 -m pip install --timeout 100 --retries 10 -r requirements.txt
        python3 -m pip install --timeout 100 --retries 10 -r docker/requirements.txt
        python3 -m pip install --timeout 100 --retries 10 -r metric_providers/psu/energy/ac/xgboost/machine/model/requirements.txt
    fi

}

function checkout_submodules() {
    print_message "Checking out further git submodules ..."

    if [[ $(uname) != "Darwin" ]]; then
        git submodule update --init lib/sgx-software-enable
    fi
    git submodule update --init metric_providers/psu/energy/ac/xgboost/machine/model
    if [[ $enterprise == true ]] ; then
        git submodule update --init ee
    fi
}

function build_binaries() {

    print_message "Building binaries ..."
    local metrics_subdir="metric_providers"
    local parent_dir="./$metrics_subdir"
    local make_file="Makefile"
    find "$parent_dir" -type d |
    while IFS= read -r subdir; do
        local make_path="$subdir/$make_file"
        if [[ -f "$make_path" ]]; then
            if [[ $(uname) == "Darwin" ]] && [[ ! "$make_path" == *"/mach/"* ]]; then
                continue
            fi
            if [[ $(uname) == "Linux" ]] && [[ "$make_path" == *"/mach/"* ]]; then
                continue
            fi
            if [[ "$make_path" == *"/lmsensors/"* ]] && [[ "${install_sensors}" == false ]]; then
                continue
            fi
            echo "Installing $subdir/metric-provider-binary ..."
            rm -f $subdir/metric-provider-binary 2> /dev/null
            make -C $subdir
        fi
    done
}

function build_containers() {

    if [[ $build_docker_containers == true ]] ; then
        print_message "Building / Updating docker containers"
        if docker info 2>/dev/null | grep rootless || [[ $(uname) == "Darwin" ]]; then
            print_message "Docker is running in rootless/VM mode. Using non-sudo call ..."
            docker compose -f docker/compose.yml down
            docker compose -f docker/compose.yml build
            docker compose -f docker/compose.yml pull
        else
            print_message "Docker is running in default root mode. Using sudo call ..."
            sudo docker compose -f docker/compose.yml down
            sudo docker compose -f docker/compose.yml build
            sudo docker compose -f docker/compose.yml pull
        fi
    fi
}

function finalize() {
    # kill the sudo timestamp
    sudo -k

    echo ""
    echo -e "${GREEN}Successfully installed Green Metrics Tool!${NC}"
    echo -e "Please remember to always activate your venv when using the GMT with 'source venv/bin/activate'"

    if $reboot_echo_flag; then
        echo -e "${GREEN}If you have newly requested to mount /tmp as tmpfs please reboot your system now.${NC}"
    fi
}

function generate_unique_hash() {
    if [[ $(uname) == "Darwin" ]]; then
        system_profiler SPHardwareDataType | awk '/Serial Number/ {print $4}'
    else
        cat /etc/machine-id
    fi
}

function send_ping() {
    local unique_hash=$(generate_unique_hash)
    local random_hash=$(openssl rand -hex 8)
    local arch=$(uname -m)
    local os=$(uname -s)
    local os_version=$(uname -r)

    curl -i -X POST https://plausible.io/api/event \
        -H "User-Agent: ${random_hash}" \
        -H 'Content-Type: application/json' \
        --data "{\"name\":\"install\",\"url\":\"http://hello.green-coding.io/install\",\"domain\":\"hello.green-coding.io\",\"props\":{\"unique_hash\":\"${unique_hash}\",\"arch\":\"${arch}\",\"os\":\"${os}\",\"os_version\":\"${os_version}\"}}" > /dev/null
}

while getopts "p:a:m:nhtbisyrlc:k:e:zZ" o; do
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
        b)
            build_docker_containers=false
            ;;
        h)
            modify_hosts=false
            ;;
        n)
            install_python_packages=false
            ;;
        t)
            ask_tmpfs=false
            ;;
        i)
            install_ipmi=false
            ;;
        s)
            install_sensors=false
            ;;
        r)
            install_msr_tools=false
            ;;
        y)
            use_system_site_packages=true
            ;;
        l)
            enable_ssl=false
            ask_ssl=false
            ;;
        x)
            build_sgx=false
            ;;
        c)
            cert_file=${OPTARG}
            ;;
        k)
            cert_key=${OPTARG}
            ;;
        e)
            ee_token=${OPTARG}
            enterprise=true
            ;;
        z)
            ask_ping=false
            ;;
        Z)
            force_send_ping=true
            ;;
    esac
done

if [[ $enterprise == true ]] ; then
    echo "Validating enterprise token"
    curl --silent -X POST https://plausible.io/api/event \
         -H 'Content-Type: application/json' \
         --data "{\"name\":\"api_test\",\"url\":\"https://www.green-coding.io/?utm_source=${ee_token}\",\"domain\":\"proxy.green-coding.io\"}" > /dev/null
fi


if [[ $ask_ssl == true ]] ; then
    echo ""
    read -p "Do you want to enable SSL for the API and frontend? (y/N) : " enable_ssl_input
    if [[  "$enable_ssl_input" == "Y" || "$enable_ssl_input" == "y" ]] ; then
        enable_ssl=true
        if [[ -z $cert_key ]]; then
            echo ""
            read -p "Please type your file where your key is located. For instance /home/me/key.pem : " cert_key
        fi
        cp $cert_key docker/nginx/ssl/production.key
        if [[ -z $cert_file ]]; then
            echo ""
            read -p "Please type your file where your certificate is located. For instance /home/me/cert.crt : " cert_file
        fi
        cp $cert_file docker/nginx/ssl/production.crt
    else
        enable_ssl=false
    fi
fi


if [[ -z $api_url ]] ; then
    echo ""
    echo "Please enter the desired API endpoint URL"
    read -p "Use port 9142 for local installs and no port for production to auto-use 80/443: (default: http://api.green-coding.internal:9142): " api_url
    api_url=${api_url:-"http://api.green-coding.internal:9142"}
fi

if [[ -z $metrics_url ]] ; then
    echo ""
    echo "Please enter the desired metrics dashboard URL"
    read -p "Use port 9142 for local installs and no port for production to auto-use 80/443: (default: http://metrics.green-coding.internal:9142): " metrics_url
    metrics_url=${metrics_url:-"http://metrics.green-coding.internal:9142"}
fi


if [[ -f config.yml ]]; then
    password_from_file=$(awk '/postgresql:/ {flag=1; next} flag && /password:/ {print $2; exit}' config.yml)
fi

default_password=${password_from_file:-$(generate_random_password 12)}

if [[ -z "$db_pw" ]] ; then
    echo ""
    read -sp "Please enter the new password to be set for the PostgreSQL DB (default: $default_password): " db_pw
    echo "" # force a newline, because read -sp will consume it
    db_pw=${db_pw:-"$default_password"}
fi

send_ping_input=false
if [[ $ask_ping == true ]]; then
    echo ""
    read -p "Developing software can be a lonely business. Want to let us know you are installing the GMT? No personal data will be shared! (y/N) : " send_ping_input
    force_send_ping=false # if by a misconfiguration or future change the user will ever be asked and says no, we never want to force send a ping - this is just an extra guard clause
fi

if [[ $force_send_ping == true || "$send_ping_input" == "Y" || "$send_ping_input" == "y" ]] ; then
    send_ping
fi
