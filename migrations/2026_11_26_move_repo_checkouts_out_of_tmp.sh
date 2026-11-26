#!/usr/bin/env bash
set -euo pipefail

# GMT now checks out repositories and relations to /var/tmp/green-metrics-tool/{repo,relations} instead of
# /tmp/green-metrics-tool/{repo,relations}, as /tmp is typically a tmpfs and the checkouts would stay in RAM.
# The old folders are not used anymore and can be removed. Run this once on every measurement machine.
#
# Not needed on Windows, where both locations are the same temporary folder.

for folder in /tmp/green-metrics-tool/repo /tmp/green-metrics-tool/relations; do
    if [[ -L "$folder" ]]; then
        echo "Skipping $folder as it is a symlink. Please check and remove it manually."
    elif [[ -d "$folder" ]]; then
        echo "Removing $folder"
        rm -rf -- "$folder"
    else
        echo "$folder not present. Nothing to do."
    fi
done
