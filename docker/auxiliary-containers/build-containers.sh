#!/bin/bash

set -euo pipefail

# the first arguement should be the version number

version=$1

# check that version is a non-empty string representing a number
if ! [[ ${version} =~ ^[0-9]+$ ]]; then
  echo "Usage: $0 <version-number>"
  echo "Example: $0 1"
  exit 1
fi

# The names of the folders within "auxiliary-containers" must match the repository name in dockerhub!

# Get the list of subdirectories within "auxiliary-containers" directory containing a Dockerfile
subdirs=($(find ./docker/auxiliary-containers -type f -name 'Dockerfile' -exec dirname {} \;))

# Loop through each subdirectory, build and push the Docker image
for subdir in "${subdirs[@]}"; do
  folder=$(basename "${subdir}")
  docker buildx build \
    --push \
    --tag "greencoding/${folder}:v1.${version}" \
    --platform linux/amd64,linux/arm64 \
    "${subdir}"
done