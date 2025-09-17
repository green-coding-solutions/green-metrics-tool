#!/usr/bin/env bash

set -euo pipefail

echo "This script works only locally as it exports from the docker container directly!"

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
mkdir -p "$SCRIPT_DIR/backup"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$SCRIPT_DIR/backup/green-coding-backup_${TIMESTAMP}"
MANIFEST_FILE="$BACKUP_DIR/backup_manifest.txt"

echo "Creating per-table backup of green-coding database..."
echo "Backup will be saved to: $BACKUP_DIR"

mkdir -p "$BACKUP_DIR"

# Get list of all tables from the database
echo "Getting list of tables..."
TABLES=$(docker exec green-coding-postgres-container psql -U postgres -p 9573 -d green-coding -t -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;")

if [ -z "$TABLES" ]; then
    echo "Error: No tables found in the database!"
    exit 1
fi

# Initialize manifest file
echo "# Backup Manifest - Generated on $(date)" > "$MANIFEST_FILE"
echo "# Format: TABLE_NAME STATUS FILE_SIZE" >> "$MANIFEST_FILE"
echo "" >> "$MANIFEST_FILE"

TOTAL_TABLES=$(echo "$TABLES" | wc -l)
CURRENT_TABLE=0
FAILED_TABLES=0
TOTAL_SIZE=0

echo "Found $TOTAL_TABLES tables to backup..."
echo ""

# Backup each table individually
for table in $TABLES; do
    # Remove any leading/trailing whitespace
    table=$(echo "$table" | tr -d '[:space:]')

    if [ -z "$table" ]; then
        continue
    fi

    CURRENT_TABLE=$((CURRENT_TABLE + 1))
    TABLE_FILE="$BACKUP_DIR/${table}.sql"

    echo "[$CURRENT_TABLE/$TOTAL_TABLES] Backing up table: $table"

    # Backup individual table
    if docker exec green-coding-postgres-container pg_dump -U postgres -p 9573 -d green-coding --clean --if-exists --table="$table" > "$TABLE_FILE" 2>/dev/null; then
        TABLE_SIZE=$(du -b "$TABLE_FILE" | cut -f1)
        TABLE_SIZE_HUMAN=$(du -h "$TABLE_FILE" | cut -f1)
        TOTAL_SIZE=$((TOTAL_SIZE + TABLE_SIZE))

        echo "  ✓ Success - Size: $TABLE_SIZE_HUMAN"
        echo "$table SUCCESS $TABLE_SIZE_HUMAN" >> "$MANIFEST_FILE"
    else
        echo "  ✗ Failed to backup table: $table"
        echo "$table FAILED 0B" >> "$MANIFEST_FILE"
        FAILED_TABLES=$((FAILED_TABLES + 1))

        # Remove the failed backup file if it exists
        [ -f "$TABLE_FILE" ] && rm "$TABLE_FILE"
    fi
done

echo ""
echo "Backup completed!"
echo "Successfully backed up: $((TOTAL_TABLES - FAILED_TABLES))/$TOTAL_TABLES tables"

if [ $FAILED_TABLES -gt 0 ]; then
    echo "Failed tables: $FAILED_TABLES"
fi

TOTAL_SIZE_HUMAN=$(numfmt --to=iec --suffix=B $TOTAL_SIZE)
echo "Total backup size: $TOTAL_SIZE_HUMAN"
echo "Backup location: $BACKUP_DIR"
echo "Manifest file: $MANIFEST_FILE"

# Add summary to manifest
{
    echo ""
    echo "# BACKUP SUMMARY"
    echo "# Total tables: $TOTAL_TABLES"
    echo "# Successful: $((TOTAL_TABLES - FAILED_TABLES))"
    echo "# Failed: $FAILED_TABLES"
    echo "# Total size: $TOTAL_SIZE_HUMAN"
    echo "# Backup completed: $(date)"
} >> "$MANIFEST_FILE"

if [ $FAILED_TABLES -gt 0 ]; then
    echo "Warning: Some tables failed to backup. Check $MANIFEST_FILE for details."
    exit 1
else
    echo "All tables backed up successfully!"
    exit 0
fi
