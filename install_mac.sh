#!/usr/bin/env bash
set -euo pipefail

if [[ $(uname) != "Darwin" ]]; then
  echo "Error: This script can only be run on macOS."
  exit 1
fi

source lib/install_shared.sh

prepare_config

checkout_submodules

setup_python

build_containers

if [[ $activate_scenario_runner == true ]] ; then

    print_message "Installing needed binaries for building ..."
    if ! command -v stdbuf &> /dev/null; then
        print_message "Trying to install 'coreutils' via homebrew. If this fails (because you do not have brew or use another package manager), please install it manually ..."
        brew install coreutils
    fi

    print_message "Building C libs"
    make -C "lib/c"

    build_binaries

    print_message "Adding powermetrics to sudoers file"
    check_file_permissions "/usr/bin/powermetrics"
    check_file_permissions "/usr/bin/killall"
    echo "${USER} ALL=(ALL) NOPASSWD:/usr/bin/powermetrics" | sudo tee /etc/sudoers.d/green_coding_powermetrics
    echo "${USER} ALL=(ALL) NOPASSWD:/usr/bin/killall powermetrics" | sudo tee /etc/sudoers.d/green_coding_kill_powermetrics
    echo "${USER} ALL=(ALL) NOPASSWD:/usr/bin/killall -9 powermetrics" | sudo tee /etc/sudoers.d/green_coding_kill_powermetrics_sigkill

fi

finalize
