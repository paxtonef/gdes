#!/bin/bash
set -euo pipefail

backup_file="$1"

if ! ./scripts/verify_backup.sh "$backup_file"; then
    exit 1
fi

restore_dir="/tmp/gdes_restore_$(date +%s)"
mkdir -p "$restore_dir"
tar -xzf "$backup_file" -C "$restore_dir"

if [ -d ~/.gdes ]; then
    mv ~/.gdes "$HOME/.gdes_archive_$(date +%Y%m%d%H%M%S)"
fi

mkdir -p ~/.gdes/inbox/{partials,canonical,reports}
cp "$restore_dir"/*/concepts/*.yaml concepts/ 2>/dev/null || true
cp "$restore_dir"/*/staging/partials/*.json ~/.gdes/inbox/partials/ 2>/dev/null || true
cp "$restore_dir"/*/staging/canonical/*.json ~/.gdes/inbox/canonical/ 2>/dev/null || true
cp "$restore_dir"/*/staging/reports/*.json ~/.gdes/inbox/reports/ 2>/dev/null || true

# Rebuild registry from export
restore_json=$(find "$restore_dir" -name "registry_export.json" 2>/dev/null | head -1)
if [ -f "$restore_json" ]; then
    .venv/bin/python -m src.gdes rebuild-registry "$restore_json"
else
    echo "WARNING: No registry_export.json found"
fi

rm -rf "$restore_dir"

# Validation
echo ""
echo "Validating restored state..."
.venv/bin/python -m src.gdes search --all > /dev/null || { echo "FAIL: Registry broken"; exit 1; }
echo "Restore complete"
.venv/bin/python -m src.gdes status
