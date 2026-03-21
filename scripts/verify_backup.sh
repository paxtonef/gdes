#!/bin/bash
backup_file="$1"

if [ ! -f "$backup_file" ]; then
    echo "ERROR: File not found"
    exit 1
fi

if ! tar -tzf "$backup_file" | grep -q "artifacts/registry_export.json"; then
    echo "ERROR: Missing registry export"
    exit 1
fi

if ! tar -xzf "$backup_file" -O */artifacts/registry_export.json 2>/dev/null | head -1 | grep -q "\["; then
    echo "ERROR: Invalid JSON"
    exit 1
fi

echo "Valid: $backup_file ($(du -h "$backup_file" | cut -f1))"
