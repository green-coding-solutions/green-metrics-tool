#!/bin/bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

function try()
{
    [[ $- = *e* ]]; SAVED_OPT_E=$?
    set +e
}

function throw()
{
    exit $1
}

function catch()
{
    export exception_code=$?
    (( $SAVED_OPT_E )) && set +e
    return $exception_code
}

db_pw=''
while getopts "p:" o; do
    case "$o" in
        p)
            db_pw=${OPTARG}
            ;;
    esac
done

if [[ -z "$db_pw" ]] ; then
    read -sp "Please enter the new password to be set for the PostgreSQL DB: " db_pw
fi

echo "Updating compose.yml with current path ..."
try
(
    cp docker/compose.yml.example docker/compose.yml
    sed -i -e "s|PATH_TO_GREEN_METRICS_TOOL_REPO|$PWD|" docker/compose.yml
    sed -i -e "s|PLEASE_CHANGE_THIS|$db_pw|" docker/compose.yml
)
catch || {
    echo -e "${RED}Error{$NC} updating compose.yml with path: $exception_code"
    throw $exception_code
}

echo "Updating config.yml with new password ..."
try
(
    cp config.yml.example config.yml
    sed -i -e "s|PLEASE_CHANGE_THIS|$db_pw|" config.yml
)
catch || {
    echo -e "${RED}Error{$NC} updating compose.yml with password: $exception_code"
    throw $exception_code
}


echo "Building metric provider binaries ..."
try
(
    metrics_subdir="tools/metric_providers"
    parent_dir="./$metrics_subdir"
    make_file="Makefile"
    find "$parent_dir" -type d |
    while IFS= read -r subdir; do
        make_path="$subdir/$make_file"
        if [[ -f "$make_path" ]]; then
            echo "Installing $subdir/metric-provider-binary ..."
            rm -f $subdir/metric-provider-binary 2> /dev/null
            make -C $subdir
        fi
    done
)
catch || {
    echo -e "${RED}Error{$NC} building metric provider binaries: $exception_code"
    throw $exception_code
}

echo "Building sgx binaries"
try
(
    make -C lib/sgx-software-enable
    mv lib/sgx-software-enable/sgx_enable tools/
    rm lib/sgx-software-enable/sgx_enable.o
)
catch || {
    echo -e "${RED}Error{$NC} building sgx binaries: $exception_code"
    throw $exception_code
}

echo "Linking DC measurement provider library file to /usr/lib"
try
(
    sudo rm -f /usr/lib/libpicohrdl.so.2
    sudo ln -s $(pwd)/tools/metric_providers/psu/energy/dc/system/libpicohrdl.so.2 /usr/lib/
)
catch || {
    echo -e "${RED}Error{$NC} linking DC provider: $exception_code"
    throw $exception_code
}

echo "Writing to /etc/hosts file..."
try
(
    etc_hosts_line_1="127.0.0.1 green-coding-postgres-container"
    etc_hosts_line_2="127.0.0.1 api.green-coding.local metrics.green-coding.local"
    if ! sudo grep -Fxq "$etc_hosts_line_1" /etc/hosts; then
        echo "$etc_hosts_line_1" | sudo tee -a /etc/hosts
    else
        echo "Entry was already present..."
    fi

    if ! sudo grep -Fxq "$etc_hosts_line_2" /etc/hosts; then
        echo "$etc_hosts_line_2" | sudo tee -a /etc/hosts
    else
        echo "Entry was already present..."
    fi
)
catch || {
    echo -e "${RED}Error{$NC} writing to hosts file: $exception_code"
    throw $exception_code
}


echo -e "${GREEN}Success installing Green Metrics Tool${NC}"
