#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'
NC='\033[0m' # No Color

db_pw=''
api_url=''
metrics_url=''
tz=''
ask_scenario_runner=true
activate_scenario_runner=true
ask_eco_ci=true
activate_eco_ci=false
ask_power_hog=true
activate_power_hog=false
ask_carbon_db=true
activate_carbon_db=false
ask_ai_optimisations=true
activate_ai_optimisations=false
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
install_nvidia_toolkit_headers=false
ee_branch=''

function print_message {
    echo ""
    echo "$1"
}

function generate_random_password() {
    local length=$1
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c "$length"
    echo
}

function check_python_version() {
    if ! python3 -c "import sys; exit(1) if (sys.version_info.major, sys.version_info.minor) < (3, 10) else exit(0)"; then
        echo 'Python version is NOT greater than or equal to 3.10. GMT requires Python 3.10 at least. Please upgrade your Python version.'
        exit 1
    fi
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

function copy_backup() {
    local file=$1
    local example_file="${file}.example"

    if [[ ! -f "$example_file" ]]; then
        echo "Error: Example file ${example_file} does not exist"
        return 1
    fi

    if [[ -f "$file" ]]; then
        print_message "Backing up existing ${file} to ${file}.backup"
        cp "$file" "${file}.backup"
    fi

    cp "$example_file" "$file"
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
    eval "${sed_command} -e \"s|__TZ__|$tz|g\" docker/compose.yml"

    print_message "Updating config.yml with new password ..."
    copy_backup config.yml
    eval "${sed_command} -e \"s|PLEASE_CHANGE_THIS|$db_pw|\" config.yml"

    print_message "Updating project with provided URLs ..."

    eval "${sed_command} -e \"s|__API_URL__|$api_url|\" config.yml"
    eval "${sed_command} -e \"s|__METRICS_URL__|$metrics_url|\" config.yml"


    copy_backup docker/nginx/api.conf
    local host_api_url=`echo $api_url | sed -E 's/^\s*.*:\/\///g'`
    local host_api_url=${host_api_url%:*}
    eval "${sed_command} -e \"s|__API_URL__|$host_api_url|\" docker/nginx/api.conf"


    copy_backup docker/nginx/block.conf

    copy_backup docker/nginx/frontend.conf
    local host_metrics_url=`echo $metrics_url | sed -E 's/^\s*.*:\/\///g'`
    local host_metrics_url=${host_metrics_url%:*}
    eval "${sed_command} -e \"s|__METRICS_URL__|$host_metrics_url|\" docker/nginx/frontend.conf"

    copy_backup frontend/js/helpers/config.js
    eval "${sed_command} -e \"s|__API_URL__|$api_url|\" frontend/js/helpers/config.js"
    eval "${sed_command} -e \"s|__METRICS_URL__|$metrics_url|\" frontend/js/helpers/config.js"

    if [[ $activate_scenario_runner == true ]]; then
        eval "${sed_command} -e \"s|__ACTIVATE_SCENARIO_RUNNER__|true|\" frontend/js/helpers/config.js"
        eval "${sed_command} -e \"s|activate_scenario_runner:.*$|activate_scenario_runner: True|\" config.yml"
    else
        eval "${sed_command} -e \"s|__ACTIVATE_SCENARIO_RUNNER__|false|\" frontend/js/helpers/config.js"
    fi

    if [[ $activate_eco_ci == true ]]; then
        eval "${sed_command} -e \"s|__ACTIVATE_ECO_CI__|true|\" frontend/js/helpers/config.js"
        eval "${sed_command} -e \"s|activate_eco_ci:.*$|activate_eco_ci: True|\" config.yml"
    else
        eval "${sed_command} -e \"s|__ACTIVATE_ECO_CI__|false|\" frontend/js/helpers/config.js"
    fi


    if [[ $enterprise == true ]]; then
        eval "${sed_command} -e \"s|#EE-ONLY#||\" docker/compose.yml"
        eval "${sed_command} -e \"s|ee_token:.*$|ee_token: ${ee_token}|\" config.yml"
    fi

    if [[ $activate_power_hog == true ]]; then
        eval "${sed_command} -e \"s|__ACTIVATE_POWER_HOG__|true|\" frontend/js/helpers/config.js"
        eval "${sed_command} -e \"s|activate_power_hog:.*$|activate_power_hog: True|\" config.yml"
    else
        eval "${sed_command} -e \"s|__ACTIVATE_POWER_HOG__|false|\" frontend/js/helpers/config.js"
    fi
    if [[ $activate_carbon_db == true ]]; then
        eval "${sed_command} -e \"s|__ACTIVATE_CARBON_DB__|true|\" frontend/js/helpers/config.js"
        eval "${sed_command} -e \"s|activate_carbon_db:.*$|activate_carbon_db: True|\" config.yml"
    else
        eval "${sed_command} -e \"s|__ACTIVATE_CARBON_DB__|false|\" frontend/js/helpers/config.js"
    fi
    # Activating AI Optimisations makes actually only sense in enterprise mode
    # but must run still, as we need to set the variables and replacements
    if [[ $activate_ai_optimisations == true ]]; then
        eval "${sed_command} -e \"s|__ACTIVATE_AI_OPTIMISATIONS__|true|\" frontend/js/helpers/config.js"
        eval "${sed_command} -e \"s|activate_ai_optimisations:.*$|activate_ai_optimisations: True|\" config.yml"
    else
        eval "${sed_command} -e \"s|__ACTIVATE_AI_OPTIMISATIONS__|false|\" frontend/js/helpers/config.js"
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

        local etc_hosts_line_1="127.0.0.1 green-coding-postgres-container green-coding-redis-container"
        local etc_hosts_line_2="127.0.0.1 ${host_api_url} ${host_metrics_url}"

        print_message "Writing to /etc/hosts file..."

        # Entry 1 is needed for the local resolution of the containers through the jobs.py and runner.py
        if ! sudo grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
            echo -e "\n$etc_hosts_line_1" | sudo tee -a /etc/hosts
        else
            echo "Entry was already present..."
        fi

        # Entry 2 can be external URLs. These should not resolve to localhost if not explcitely wanted
        if [[ ${host_metrics_url} == *".green-coding.internal"* ]];then
            if ! sudo grep -Fxq "$etc_hosts_line_2" /etc/hosts; then
                echo "$etc_hosts_line_2" | sudo tee -a /etc/hosts
            else
                echo "Entry was already present..."
            fi
        fi
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

    print_message "Adding python3 lib.hardware_info_root to sudoers file"
    check_file_permissions "/usr/bin/python3"
    # Please note the -m as here we will later call python3 without venv. It must understand the .lib imports
    # and not depend on venv installed packages
    echo "${USER} ALL=(ALL) NOPASSWD:/usr/bin/python3 -m lib.hardware_info_root" | sudo tee /etc/sudoers.d/green-coding-hardware-info
    echo "${USER} ALL=(ALL) NOPASSWD:/usr/bin/python3 -m lib.hardware_info_root --read-rapl-energy-filtering" | sudo tee -a /etc/sudoers.d/green-coding-hardware-info
    sudo chmod 500 /etc/sudoers.d/green-coding-hardware-info
    # remove old file name
    sudo rm -f /etc/sudoers.d/green_coding_hardware_info

    print_message "Setting the hardare hardware_info to be owned by root"
    sudo cp -f $PWD/lib/hardware_info_root_original.py $PWD/lib/hardware_info_root.py
    sudo chown root:$(id -gn root) $PWD/lib/hardware_info_root.py
    sudo chmod 755 $PWD/lib/hardware_info_root.py


    if [[ $install_python_packages == true ]] ; then
        print_message "Updating python requirements"
        python3 -m pip install --timeout 100 --retries 10 --upgrade pip
        python3 -m pip install --timeout 100 --retries 10 -r requirements.txt
        python3 -m pip install --timeout 100 --retries 10 -r docker/requirements.txt
        python3 -m pip install --timeout 100 --retries 10 -r metric_providers/psu/energy/ac/xgboost/machine/model/requirements.txt
    fi

}

function checkout_submodules() {
    if [[ $activate_scenario_runner == false ]]; then
        print_message 'Skipping checkout submodules ...'
        return
    fi

    print_message "Checking out further git submodules ..."

    if [[ $(uname) != "Darwin" ]]; then
        git submodule update --init lib/sgx-software-enable
    fi

    git submodule update --init metric_providers/psu/energy/ac/xgboost/machine/model

    if [[ $enterprise == true ]] ; then
        if [[ ! -d "ee" ]]; then
            git clone git@github.com:green-coding-solutions/gmt-enterprise.git ee
        fi

        if [[ ! -z $ee_branch ]]; then
            echo "Checking out ee branch $ee_branch"
            git -C ee fetch origin
            git -C ee checkout $ee_branch
        fi

        # Link enterprise only files to running instance. Requires the ../ee repo is present. Will be silently ingored if not
        arr=('cron/delete_expired_data.py')
        for item in "${arr[@]}"; do
            [ -e "ee/${item}" ] && ln -sf "../ee/${item}" "${item}" || { echo "Could not find enterprise source file: ee/${item}" >&2; }
        done

    fi
}

function build_binaries() {
    if [[ $activate_scenario_runner == false ]]; then
        print_message 'Skipping build binaries ...'
        return
    fi

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
            if [[ "$make_path" == *"/nvidia/"* ]] && [[ "${install_nvidia_toolkit_headers}" == false ]]; then
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
        docker compose -f docker/compose.yml down
        docker compose -f docker/compose.yml build
        docker compose -f docker/compose.yml pull
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

function check_optarg() {
    local option=$1
    local optarg=$2

    if [[ -z "$optarg" ]]; then
        echo "Error: Option -$option requires an argument, but none was provided." >&2
        exit 1
    fi

    if [[ "$optarg" == -* ]]; then
        echo "Error: Option -$option received broken argument: $optarg" >&2; exit 1;
        exit 1
    fi
}

check_python_version

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tz)
            check_optarg 'tz' "${2:-}"
            tz="$2"
            shift 2
            ;;
        --nvidia-gpu)
            install_nvidia_toolkit_headers=true
            shift
            ;;
        --ai) # This is not documented in the help, as it is only for GCS internal use
            ask_ai_optimisations=false
            activate_ai_optimisations=true
            shift
            ;;
        --no-ai) # This is not documented in the help, as it is only for GCS internal use
            ask_ai_optimisations=false
            activate_ai_optimisations=false
            shift
            ;;
        --ee-branch) # This is not documented in the help, as it is only for GCS internal use
            check_optarg 'ee-branch' "${2:-}"
            ee_branch="$2"
            shift 2
            ;;
        -p)
            check_optarg 'p' "${2:-}"
            db_pw="$2"
            shift 2
            ;;
        -a)
            check_optarg 'a' "${2:-}"
            api_url="$2"
            shift 2
            ;;
        -m)
            check_optarg 'm' "${2:-}"
            metrics_url="$2"
            shift 2
            ;;
        -B)
            build_docker_containers=false
            shift
            ;;
        -W)
            modify_hosts=false
            shift
            ;;
        -N)
            install_python_packages=false
            shift
            ;;
        -T)
            ask_tmpfs=false
            shift
            ;;
        -I)
            install_ipmi=false
            shift
            ;;
        -S)
            install_sensors=false
            shift
            ;;
        -R)
            install_msr_tools=false
            shift
            ;;
        -u)
            use_system_site_packages=true
            shift
            ;;
        -L)
            enable_ssl=false
            ask_ssl=false
            shift
            ;;
        -X)
            build_sgx=false
            shift
            ;;
        -c)
            check_optarg 'c' "${2:-}"
            cert_file="$2"
            shift 2
            ;;
        -k)
            check_optarg 'k' "${2:-}"
            cert_key="$2"
            shift 2
            ;;
        -e)
            check_optarg 'e' "${2:-}"
            ee_token="$2"
            enterprise=true
            shift 2
            ;;
        -z)
            ask_ping=false
            shift
            ;;
        -Z)
            force_send_ping=true
            shift
            ;;
        -d)
            activate_carbon_db=true
            ask_carbon_db=false
            shift
            ;;
        -D)
            activate_carbon_db=false
            ask_carbon_db=false
            shift
            ;;
        -g)
            activate_power_hog=true
            ask_power_hog=false
            shift
            ;;
        -G)
            activate_power_hog=false
            ask_power_hog=false
            shift
            ;;
        -f)
            activate_scenario_runner=true
            ask_scenario_runner=false
            shift
            ;;
        -F)
            activate_scenario_runner=false
            ask_scenario_runner=false
            shift
            ;;
        -j)
            activate_eco_ci=true
            ask_eco_ci=false
            shift
            ;;
        -J)
            activate_eco_ci=false
            ask_eco_ci=false
            shift
            ;;
        -h)
            echo 'usage: ./install_XXX [p:] [a:] [m:] [N] [h] [T] [B] [I] [S] [u] [R] [L] [c:] [k:] [e:] [z] [Z] [d] [D] [g] [G] [f] [F] [j] [J]'
            echo ''
            echo 'options:'
            echo -e '  -p DB_PW:\t\tSupply DB password'
            echo -e '  -a API_URL:\t\tSupply API URL'
            echo -e '  -m METRICS_URL:\tSupply Dashboard URL'
            echo -e '  -B:\t\t\tDo not build docker containers'
            echo -e '  -W:\t\t\tDo not Modify hosts'
            echo -e '  -N:\t\t\tDo not install Python packages'
            echo -e '  -T:\t\t\tDo not ask for tmpfs remounting'
            echo -e '  -I:\t\t\tDo not install IPMI drivers'
            echo -e '  -S:\t\t\tDo not install lm-sensors package'
            echo -e '  -R:\t\t\tDo not install MSR tools'
            echo -e '  -u:\t\t\tUse Python system packages'
            echo -e '  -L:\t\t\tDisable SSL'
            echo -e '  -X:\t\t\tDo not build SGX checking binaries'
            echo -e '  -c:\t\t\tSupply SSL .crt file'
            echo -e '  -k:\t\t\tSupply SSL .key file'
            echo -e '  -e: EE_TOKEN\t\tActivate enterprise features and store token'
            echo -e '  -z:\t\t\tDo not ask to send install telemetry ping'
            echo -e '  -Z:\t\t\tForce to send install telemetry ping'
            echo -e '  -d:\t\t\tActivate CarbonDB'
            echo -e '  -D:\t\t\tDe-activate CarbonDB'
            echo -e '  -g:\t\t\tActivate PowerHOG'
            echo -e '  -G:\t\t\tDe-activate PowerHOG'
            echo -e '  -f:\t\t\tActivate ScenarioRunner'
            echo -e '  -F:\t\t\tDe-activate ScenarioRunner'
            echo -e '  -j:\t\t\tActivate Eco CI'
            echo -e '  -J:\t\t\tDe-activate Eco CI'

            exit 0
            ;;
        ## v) y) q) # reserved, as they typically have other meaning!
        --)  # End of all options
        shift
        break
        ;;
        *)
        # Unrecognized option or no more options
        # Typically you either want to break or report an error here:
        echo "Invalid option: $1" >&2
        exit 1
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

# ---- Ask for timezone (default from system; fallback Europe/Berlin) ----
if [[ -z $tz ]] ; then
    default_tz=''
    if [[ -f /etc/timezone ]]; then
        default_tz="$(cat /etc/timezone 2>/dev/null)"
    elif [[ -L /etc/localtime ]]; then
        default_tz="$(readlink /etc/localtime 2>/dev/null | sed 's#.*/zoneinfo/##')"
    fi
    default_tz="${default_tz:-Europe/Berlin}"
    echo ""
    read -p "Enter timezone for Postgres and containers (e.g., Europe/Berlin) (default: ${default_tz}): " tz
    tz="${tz:-$default_tz}"
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

if [[ $ask_scenario_runner == true ]]; then
    echo ""
    read -p "Do you want to activate ScenarioRunner (For benchmarking container software)? (Y/n) : " activate_scenario_runner
    if [[  "$activate_scenario_runner" == "Y" || "$activate_scenario_runner" == "y" || "$activate_scenario_runner" == "" ]] ; then
        activate_scenario_runner=true
    else
        activate_scenario_runner=false
    fi
fi


if [[ $ask_eco_ci == true ]]; then
    echo ""
    read -p "Do you want to activate Eco CI (For tracking CI/CD carbon emissions)? (y/N) : " activate_eco_ci
    if [[  "$activate_eco_ci" == "Y" || "$activate_eco_ci" == "y" ]] ; then
        activate_eco_ci=true
    else
        activate_eco_ci=false
    fi
fi

if [[ $ask_carbon_db == true ]]; then
    echo ""
    read -p "Do you want to activate CarbonDB? (y/N) : " activate_carbon_db
    if [[  "$activate_carbon_db" == "Y" || "$activate_carbon_db" == "y" ]] ; then
        activate_carbon_db=true
    else
        activate_carbon_db=false
    fi
fi

if [[ $ask_power_hog == true ]]; then
    echo ""
    read -p "Do you want to activate PowerHOG? (y/N) : " activate_power_hog
    if [[  "$activate_power_hog" == "Y" || "$activate_power_hog" == "y" ]] ; then
        activate_power_hog=true
    else
        activate_power_hog=false
    fi
fi

if [[ $enterprise == true && $ask_ai_optimisations == true ]]; then
    echo ""
    read -p "Do you want to activate AI Optimizations? (y/N) : " activate_ai_optimisations
    if [[  "$activate_ai_optimisations" == "Y" || "$activate_ai_optimisations" == "y" ]] ; then
        activate_ai_optimisations=true
    else
        activate_ai_optimisations=false
    fi
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
