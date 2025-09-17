#!/usr/bin/env bash

set -euo pipefail

echo "This script works only locally as it imports into the docker container directly!"

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

read -p "You are about to drop all data in the current database and import from a backup! Sure? (y/N) : " response
if [[  "$response" == "Y" || "$response" == "y" ]] ; then

    docker exec green-coding-postgres-container psql -Upostgres -p9573 -dgreen-coding -c 'DROP schema IF EXISTS "public" CASCADE;'
    docker exec green-coding-postgres-container psql -Upostgres -p9573 -dgreen-coding -c 'CREATE SCHEMA IF NOT EXISTS "public";'
    docker exec green-coding-postgres-container psql -Upostgres -p9573 -dgreen-coding -c 'CREATE EXTENSION "uuid-ossp";'
    docker exec green-coding-postgres-container psql -Upostgres -p9573 -dgreen-coding -c 'CREATE EXTENSION "moddatetime";'

    echo "Checking for backup files in $SCRIPT_DIR/backup/import..."
    mkdir -p "$SCRIPT_DIR/backup/import"

    if ls "$SCRIPT_DIR/backup/import"/*.sql >/dev/null 2>&1; then
        echo "Files to be imported:"
        basename -a "$SCRIPT_DIR/backup/import"/*.sql
        read -p "Proceed with importing these files? (y/N): " confirm
        if [[ "$confirm" == "Y" || "$confirm" == "y" ]]; then
            echo "Starting database import..."
            cat "$SCRIPT_DIR/backup/import"/* | docker exec -i green-coding-postgres-container psql -Upostgres -p9573 -dgreen-coding
        else
            echo "Import cancelled."
            exit 0
        fi
    else
        echo "No .sql files found in $SCRIPT_DIR/backup/import/"
        echo "Please add backup files and run the script again."
        exit 1
    fi
fi
