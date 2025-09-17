#!/usr/bin/env bash

set -euo pipefail

echo "This script works only locally as it exports from the docker container directly!"

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
mkdir -p "$SCRIPT_DIR/backup"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$SCRIPT_DIR/backup/green-coding-backup_${TIMESTAMP}.sql"

echo "Creating backup of green-coding database..."
echo "Backup will be saved to: $BACKUP_FILE"

if docker exec green-coding-postgres-container pg_dump -Upostgres -p9573 -dgreen-coding --clean --if-exists > "$BACKUP_FILE"; then
    echo "Backup successfully created: $BACKUP_FILE"
    echo "File size: $(du -h "$BACKUP_FILE" | cut -f1)"
else
    echo "Error: Backup failed!"
    exit 1
fi
