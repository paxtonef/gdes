#!/bin/bash
set -euo pipefail

BACKUP_ROOT="backups"
RETENTION_DAYS=30

timestamp=$(date +%Y%m%d_%H%M%S)
backup_dir="$BACKUP_ROOT/$timestamp"
mkdir -p "$backup_dir"/{artifacts,concepts,staging/{partials,canonical,reports}}

# Create deterministic manifest
artifact_count=$(.venv/bin/python -m src.gdes search --all --json 2>/dev/null | jq '. | length' || echo "0")
concept_files=$(ls concepts/*.yaml 2>/dev/null | wc -l | tr -d ' ')

cat > "$backup_dir/manifest.json" <<EOF
{
  "snapshot_id": "$timestamp",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "gdes_version": "v1.3",
  "includes": ["concepts", "staging", "registry_export"],
  "counts": {
    "artifacts": $artifact_count,
    "concepts": $concept_files
  }
}
EOF

.venv/bin/python -m src.gdes search --all --json > "$backup_dir/artifacts/registry_export.json"
cp concepts/*.yaml "$backup_dir/concepts/"
cp ~/.gdes/inbox/partials/*.json "$backup_dir/staging/partials/" 2>/dev/null || true
cp ~/.gdes/inbox/canonical/*.json "$backup_dir/staging/canonical/" 2>/dev/null || true
cp ~/.gdes/inbox/reports/*.json "$backup_dir/staging/reports/" 2>/dev/null || true
.venv/bin/python -m src.gdes status > "$backup_dir/status.txt"

tar -czf "$backup_dir.tar.gz" -C "$BACKUP_ROOT" "$timestamp"
rm -rf "$backup_dir"

find "$BACKUP_ROOT" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

echo "Backup: $backup_dir.tar.gz ($(du -h "$backup_dir.tar.gz" | cut -f1))"
