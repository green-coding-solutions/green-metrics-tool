#!/usr/bin/env bash
set -euo pipefail

if [ -z "${1-}" ]; then
  echo "Please supply mode as first argument. Either 'ai', 'website', 'command-host', 'command-container', 'command-qemu', or 'command-cloud-hypervisor'"
  exit 1
fi


GMT_ROOT_DIR="$(cd "$(dirname "${0}")" && pwd)"

if [[ "$1" == "website" ]]; then
    if [ -z "${2-}" ]; then
      echo "Please supply the website as second argument with scheme. Example: https://www.example.com"
      exit 1
    fi

    if [[ -n "${3-}" && "${3-}" == '--quick' ]]; then
        python3 "${GMT_ROOT_DIR}/runner.py" --uri ${GMT_ROOT_DIR} --filename 'templates/website/usage_scenario.yml' --variable __GMT_VAR_PAGE__="${2}" --variable __GMT_VAR_SLEEP__=0 --dev-no-sleeps --dev-no-system-checks --dev-cache-build --skip-optimizations ${4-} ${5-} ${6-} ${7-} ${8-}
    else
        python3 "${GMT_ROOT_DIR}/runner.py" --uri ${GMT_ROOT_DIR} --filename 'templates/website/usage_scenario.yml' --variable __GMT_VAR_PAGE__="${2}" --variable __GMT_VAR_SLEEP__=5 ${3-} ${4-} ${5-} ${6-} ${7-} ${8-}
    fi

elif [[ "$1" == "ai" ]]; then
    if [ -z "${2-}" ]; then
      echo "Please supply the prompt as second argument in single quotes. Example: 'How cool is the GMT?' "
      exit 1
    fi
    if [[ -n "${3-}" && "${3-}" == '--quick' ]]; then
        python3 "${GMT_ROOT_DIR}/runner.py" --uri ${GMT_ROOT_DIR} --filename 'templates/ai/usage_scenario.yml' --variable __GMT_VAR_MODEL__="gemma3:1b" --variable __GMT_VAR_PROMPT__="${2}"  --dev-no-sleeps --dev-no-system-checks --dev-cache-build --skip-optimizations --allow-unsafe ${4-} ${5-} ${6-} ${7-} ${8-}
    else
        python3 "${GMT_ROOT_DIR}/runner.py" --uri ${GMT_ROOT_DIR} --filename 'templates/ai/usage_scenario.yml' --variable __GMT_VAR_MODEL__="gemma3:1b" --variable __GMT_VAR_PROMPT__="${2}" --allow-unsafe ${3-} ${4-} ${5-} ${6-} ${7-} ${8-}
    fi
elif [[ "$1" == "command-host" || "$1" == "command-container" || "$1" == "command-qemu" || "$1" == "command-cloud-hypervisor" ]]; then
    if [ -z "${2-}" ]; then
      echo "Please supply the command as second argument in single quotes. Example: 'stress-ng --cpu 1 --timeout 5s'"
      exit 1
    fi

    if [[ "$1" == "command-host" ]]; then
        COMMAND_TEMPLATE='templates/command/usage_scenario_host.yml'
    elif [[ "$1" == "command-container" ]]; then
        COMMAND_TEMPLATE='templates/command/usage_scenario_docker.yml'
    elif [[ "$1" == "command-qemu" ]]; then
        COMMAND_TEMPLATE='templates/command/usage_scenario_kata_qemu.yml'
    elif [[ "$1" == "command-cloud-hypervisor" ]]; then
        COMMAND_TEMPLATE='templates/usage_scenario_kata_cloud_hypervisor.yml'
    fi

    if [[ -n "${3-}" && "${3-}" == '--quick' ]]; then
        python3 "${GMT_ROOT_DIR}/runner.py" --uri ${GMT_ROOT_DIR} --filename "${COMMAND_TEMPLATE}" --variable __GMT_VAR_COMMAND__="${2}" --dev-no-sleeps --dev-no-system-checks --dev-cache-build --skip-optimizations --dev-no-container-dependency-collection ${4-} ${5-} ${6-} ${7-} ${8-}
    else
        python3 "${GMT_ROOT_DIR}/runner.py" --uri ${GMT_ROOT_DIR} --filename "${COMMAND_TEMPLATE}" --variable __GMT_VAR_COMMAND__="${2}" ${3-} ${4-} ${5-} ${6-} ${7-} ${8-}
    fi
else
    echo "Unknown mode ${1} - Only 'ai', 'website', 'command-host', 'command-container', 'command-qemu', and 'command-cloud-hypervisor' supported."
    exit 1
fi

