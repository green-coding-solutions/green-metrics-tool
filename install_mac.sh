#!/bin/bash
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

print_message "Installing needed binaries for building ..."
if ! command -v stdbuf &> /dev/null; then
    print_message "Trying to install 'coreutils' via homebew. If this fails (because you do not have brew or use another package manager), please install it manually ..."
    brew install coreutils
fi

print_message "Building C libs"
make -C "lib/c"

build_binaries

print_message "Setting up powermetrics in sudoers files"
check_file_permissions "/usr/bin/powermetrics"
check_file_permissions "/usr/bin/killall"

check_and_write() {
  local file="$1"
  local content="$2"

  if !grep -Fxq "$content" "$file" 2>/dev/null; then
    echo "$content" | sudo tee "$file" > /dev/null
    echo "Updated $file."
  fi
}

check_and_write "/etc/sudoers.d/green_coding_powermetrics" "${USER} ALL=(ALL) NOPASSWD:/usr/bin/powermetrics"
check_and_write "/etc/sudoers.d/green_coding_kill_powermetrics" "${USER} ALL=(ALL) NOPASSWD:/usr/bin/killall powermetrics"
check_and_write "/etc/sudoers.d/green_coding_kill_powermetrics_sigkill" "${USER} ALL=(ALL) NOPASSWD:/usr/bin/killall -9 powermetrics"


finalize