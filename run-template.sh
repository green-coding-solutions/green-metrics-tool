# we are omitting the shebang as we want just the shell of the user to execute it and not limit to bash
set -euo pipefail

if [ -z "${1-}" ]; then
  echo "Please supply mode as first argument. Either 'ai' or 'website'"
  exit 1
fi


GMT_ROOT_DIR="$(cd "$(dirname "${0}")" && pwd)"

if [[ "$1" == "website" ]]; then
    if [ -z "${2-}" ]; then
      echo "Please supply the website as second argument with scheme. Example: https://www.example.com"
      exit 1
    fi

    if [[ -n "${3-}" && "${3-}" == '--quick' ]]; then
        python3 "${GMT_ROOT_DIR}/runner.py" --uri ${GMT_ROOT_DIR} --filename 'templates/website/usage_scenario.yml' --variables __GMT_VAR_PAGE__="${2}" __GMT_VAR_SLEEP_1__=0 __GMT_VAR_SLEEP_2__=0 --dev-no-sleeps --skip-system-checks --dev-cache-build --dev-no-optimizations ${4-} ${5-}
    else
        python3 "${GMT_ROOT_DIR}/runner.py" --uri ${GMT_ROOT_DIR} --filename 'templates/website/usage_scenario.yml' --variables __GMT_VAR_PAGE__="${2}" __GMT_VAR_SLEEP_1__=2 __GMT_VAR_SLEEP_2__=5 ${3-} ${4-}
    fi

elif [[ "$1" == "ai" ]]; then
    if [ -z "${2-}" ]; then
      echo "Please supply the prompt as second argument in single quotes. Example: 'How cool is the GMT?' "
      exit 1
    fi
    if [[ -n "${3-}" && "${3-}" == '--quick' ]]; then
        python3 "${GMT_ROOT_DIR}/runner.py" --uri ${GMT_ROOT_DIR} --filename 'templates/ai/usage_scenario.yml' --variables __GMT_VAR_MODEL__="gemma3:1b" __GMT_VAR_PROMPT__="${2}"  --dev-no-sleeps --skip-system-checks --dev-cache-build --dev-no-optimizations --allow-unsafe ${4-} ${5-}
    else
        python3 "${GMT_ROOT_DIR}/runner.py" --uri ${GMT_ROOT_DIR} --filename 'templates/ai/usage_scenario.yml' --variables __GMT_VAR_MODEL__="gemma3:1b" __GMT_VAR_PROMPT__="${2}" --allow-unsafe ${3-} ${4-}
    fi
else
    echo "Unknown mode ${1} - Only 'ai' and 'website' supported."
    exit 1
fi

