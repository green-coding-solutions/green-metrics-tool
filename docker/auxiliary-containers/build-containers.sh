#!/bin/bash

set -euo pipefail

# The names of the folders within "auxiliary-containers" must match the repository name in dockerhub!

# Get the list of subdirectories within "auxiliary-containers" directory containing a Dockerfile
subdirs=($(find ./docker/auxiliary-containers -type f -name 'Dockerfile' -exec dirname {} \;))

# Loop through each subdirectory, build and push the Docker image
for subdir in "${subdirs[@]}"; do
  folder=$(basename "${subdir}")
  docker buildx build \
    --push \
    --tag "greencoding/${folder}:latest" \
    --platform linux/amd64,linux/arm64 \
    "${subdir}"
done