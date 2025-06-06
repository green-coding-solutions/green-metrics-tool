#!/usr/bin/env bash

set -euo pipefail

output_directory="$(dirname $0)/frontend/js/api/"

rm -rf "${output_directory}"

openapi-generator-cli generate \
  --generator-name javascript \
  --input-spec http://127.0.0.1:8000/openapi.json \
  --output "${output_directory}" \
  --skip-validate-spec \
  --global-property apiDocs=false \
  --global-property apiTests=false \
  --global-property modelDocs=false \
  --global-property modelTests=false \
  --additional-properties usePromises=true
