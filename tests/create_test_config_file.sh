#!/bin/bash
set -euo pipefail

cp test-config.yml.example test-config.yml

if [[ $(uname) == "Darwin" ]]; then
    sed -i '' 's/#ee_token:/ee_token:/' test-config.yml
else
b    sed -i 's/#ee_token:/ee_token:/' test-config.yml
fi
