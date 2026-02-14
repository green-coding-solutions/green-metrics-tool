#!/usr/bin/env bash

set -euo pipefail

echo "This script works only locally as it imports into the docker container directly!"

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
BACKUP_BASE_DIR="$SCRIPT_DIR/backup"
BACKUP_PREFIX="green-coding-backup_"

# Function to list available backups
list_backups() {
    echo "Available backups:"
    local backup_count=0

    # Check for per-table format backups
    while IFS= read -r -d '' backup_dir; do
        if [ -d "$backup_dir" ] && [ -f "$backup_dir/backup_manifest.txt" ]; then
            backup_count=$((backup_count + 1))
            local backup_name
            backup_name=$(basename "$backup_dir")
            local table_count
            table_count=$(grep -c "SUCCESS" "$backup_dir/backup_manifest.txt" 2>/dev/null || echo "unknown")
            local backup_size
            backup_size=$(grep "# Total size:" "$backup_dir/backup_manifest.txt" | cut -d: -f2 | tr -d ' ' 2>/dev/null || echo "unknown")
            echo "  $backup_count) $backup_name ($table_count tables, $backup_size)"
        fi
    done < <(find "$BACKUP_BASE_DIR" -maxdepth 1 -name "${BACKUP_PREFIX}*" -print0 2>/dev/null)

    # Check for single-file format backups
    mkdir -p "$BACKUP_BASE_DIR/import"
    if ls "$BACKUP_BASE_DIR/import"/*.sql >/dev/null 2>&1; then
        backup_count=$((backup_count + 1))
        local file_count
        file_count=$(find "$BACKUP_BASE_DIR/import" -name "*.sql" | wc -l)
        local total_size
        total_size=$(du -sh "$BACKUP_BASE_DIR/import" | cut -f1)
        local file_names
        file_names=$(find "$BACKUP_BASE_DIR/import" -name "*.sql" -exec basename {} \; | tr '\n' ', ' | sed 's/,$//')
        echo "  $backup_count) Single-file import directory ($file_count files, $total_size: $file_names)"
    fi

    echo "$backup_count"
}

# Function to select backup
select_backup() {
    local backup_dirs=()
    local selection

    # Collect per-table format backups
    while IFS= read -r -d '' backup_dir; do
        if [ -d "$backup_dir" ] && [ -f "$backup_dir/backup_manifest.txt" ]; then
            backup_dirs+=("$backup_dir")
        fi
    done < <(find "$BACKUP_BASE_DIR" -maxdepth 1 -name "${BACKUP_PREFIX}*" -print0 2>/dev/null)

    # Add single-file import directory if it has files
    if ls "$BACKUP_BASE_DIR/import"/*.sql >/dev/null 2>&1; then
        backup_dirs+=("$BACKUP_BASE_DIR/import")
    fi

    if [ ${#backup_dirs[@]} -eq 0 ]; then
        echo "No backup directories found!"
        echo "Please create a backup first or add files to $BACKUP_BASE_DIR/import/"
        exit 1
    fi

    echo ""
    read -r -p "Select backup to import (1-${#backup_dirs[@]}): " selection || {
        echo ""
        echo "No input received. Exiting."
        exit 1
    }

    if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le ${#backup_dirs[@]} ]; then
        echo "${backup_dirs[$((selection-1))]}"
    else
        echo "ERROR: Invalid selection!" >&2
        exit 1
    fi
}

# Function to import per-table backup
import_per_table_backup() {
    local backup_dir="$1"
    local manifest_file="$backup_dir/backup_manifest.txt"

    echo "Reading backup manifest from $(basename "$backup_dir")..."

    # Get list of successful tables from manifest
    local tables=()
    while IFS= read -r line; do
        if [[ "$line" =~ ^([a-zA-Z_][a-zA-Z0-9_]*)[[:space:]]+SUCCESS ]]; then
            tables+=("${BASH_REMATCH[1]}")
        fi
    done < "$manifest_file"

    if [ ${#tables[@]} -eq 0 ]; then
        echo "No successful table backups found in manifest!"
        exit 1
    fi

    echo "Found ${#tables[@]} tables to import:"
    printf "  %s\n" "${tables[@]}"
    echo ""

    read -r -p "Proceed with importing these tables? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "Import cancelled."
        exit 0
    fi

    echo ""
    echo "Starting per-table import..."

    local current_table=0
    local failed_tables=0
    local total_tables=${#tables[@]}

    for table in "${tables[@]}"; do
        current_table=$((current_table + 1))
        local table_file="$backup_dir/${table}.sql"

        echo "[$current_table/$total_tables] Importing table: $table"

        if [ -f "$table_file" ]; then
            if docker exec -i green-coding-postgres-container psql -U postgres -p 9573 -d green-coding < "$table_file" >/dev/null 2>&1; then
                echo "  ✓ Success"
            else
                echo "  ✗ Failed to import table: $table"
                failed_tables=$((failed_tables + 1))
            fi
        else
            echo "  ✗ Table file not found: $table_file"
            failed_tables=$((failed_tables + 1))
        fi
    done

    echo ""
    echo "Import completed!"
    echo "Successfully imported: $((total_tables - failed_tables))/$total_tables tables"

    if [ $failed_tables -gt 0 ]; then
        echo "Failed tables: $failed_tables"
        echo "Warning: Some tables failed to import."
        exit 1
    else
        echo "All tables imported successfully!"
    fi
}

# Function to import single-file backup
import_single_file_backup() {
    local import_dir="$1"

    echo "Files to be imported:"
    basename -a "$import_dir"/*.sql
    echo ""

    read -r -p "Proceed with importing these files? (y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        echo "Starting single-file database import..."
        if cat "$import_dir"/* | docker exec -i green-coding-postgres-container psql -U postgres -p 9573 -d green-coding; then
            echo "Single-file import completed successfully!"
        else
            echo "Single-file import failed!"
            exit 1
        fi
    else
        echo "Import cancelled."
        exit 0
    fi
}

# Main script logic
echo ""

# List and select backup first
backup_output=$(list_backups)
backup_count=$(echo "$backup_output" | tail -n 1)
echo "$backup_output" | head -n -1

if [ "$backup_count" -eq 0 ]; then
    echo "No backups found!"
    exit 1
fi

if ! selected_backup=$(select_backup | tr -d '\n'); then
    echo "Failed to select backup. Exiting."
    exit 1
fi

if [ -z "$selected_backup" ]; then
    echo "No backup selected. Exiting."
    exit 1
fi

echo ""
if [ -f "$selected_backup/backup_manifest.txt" ]; then
    echo "Selected backup: $(basename "$selected_backup") (per-table format)"
else
    file_list=$(find "$selected_backup" -name "*.sql" -exec basename {} \; | tr '\n' ', ' | sed 's/,$//')
    echo "Selected backup: Single-file format ($file_list)"
fi
echo ""

read -r -p "You are about to drop all data in the current database and import from this backup! Sure? (y/N) : " response
if [[ "$response" =~ ^[Yy]$ ]]; then

    echo ""
    echo "Preparing database for import..."

    # Drop and recreate schema
    docker exec green-coding-postgres-container psql -U postgres -p 9573 -d green-coding -c 'DROP schema IF EXISTS "public" CASCADE;'
    docker exec green-coding-postgres-container psql -U postgres -p 9573 -d green-coding -c 'CREATE SCHEMA IF NOT EXISTS "public";'
    docker exec green-coding-postgres-container psql -U postgres -p 9573 -d green-coding -c 'CREATE EXTENSION "uuid-ossp";'
    docker exec green-coding-postgres-container psql -U postgres -p 9573 -d green-coding -c 'CREATE EXTENSION "moddatetime";'

    echo "Database prepared successfully!"
    echo ""

    # Import based on backup type
    if [ -f "$selected_backup/backup_manifest.txt" ]; then
        import_per_table_backup "$selected_backup"
    else
        import_single_file_backup "$selected_backup"
    fi

else
    echo "Import cancelled."
    exit 0
fi
