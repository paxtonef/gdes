#!/bin/bash
set -euo pipefail

backup_file="$1"

if ! ./scripts/verify_backup.sh "$backup_file"; then
    exit 1
fi

restore_dir="/tmp/gdes_restore_$(date +%s)"
tar -xzf "$backup_file" -C "$restore_dir"

if [ -d ~/.gdes ]; then
    mv ~/.gdes "$HOME/.gdes_archive_$(date +%Y%m%d%H%M%S)"
fi

mkdir -p ~/.gdes/inbox/{partials,canonical,reports}
cp "$restore_dir"/*/concepts/*.yaml concepts/ 2>/dev/null || true
cp "$restore_dir"/*/staging/partials/*.json ~/.gdes/inbox/partials/ 2>/dev/null || true
cp "$restore_dir"/*/staging/canonical/*.json ~/.gdes/inbox/canonical/ 2>/dev/null || true
cp "$restore_dir"/*/staging/reports/*.json ~/.gdes/inbox/reports/ 2>/dev/null || true

rm -rf "$restore_dir"
echo "Restore complete. Verify: .venv/bin/python -m gdes status"
