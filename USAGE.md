# GDES — Usage Reference

## Concept File Location Priority

GDES resolves concepts in this order (first match wins):

1. **Project-local**: `./concepts/{concept_id}.yaml`
2. **Configured path**: (if set in config)
3. **User home**: `~/.gdes/concepts/{concept_id}.yaml`

Run from your project root to use local concepts.

---

## Pipeline

Ingest a file into the registry:

    python -m src.gdes pipeline --file myfile.yaml --concept config --type yaml

Failure behaviour:
- Missing concept: clean error, paths shown, no traceback
- Wrong type: rejected at Stage B, rolled back automatically
- Failed runs clean up automatically (zero-orphan guarantee)

---

## Search & Status

    python -m src.gdes search --concept finance --json
    python -m src.gdes status
    python -m src.gdes health

---

## Linking

    python -m src.gdes link <id1> <id2>
    python -m src.gdes refs <id>
    python -m src.gdes show-links <id>
    python -m src.gdes validate-links

---

## Graph Traversal (V1.7+)

Basic traversal:

    python -m src.gdes neighbors <id>
    python -m src.gdes subgraph <id> --depth 2
    python -m src.gdes path <id1> <id2>

---

## Filtered Traversal (V1.8)

Filter by concept:

    python -m src.gdes neighbors <id> --concept finance
    python -m src.gdes subgraph <id> --depth 2 --concept finance
    python -m src.gdes path <id1> <id2> --concept security

Filter by type:

    python -m src.gdes subgraph <id> --depth 2 --type invoice
    python -m src.gdes path <id1> <id2> --type alert

Combined filters:

    python -m src.gdes subgraph <id> --depth 2 --concept security --type alert

Filter behaviour:
- Start node is always included in subgraph regardless of filters
- Intermediate and destination nodes must satisfy filters for path
- No-match returns empty list, not an error

---

## Advanced Queries (V1.9)

Cycle detection:

    python -m src.gdes detect-cycles
    python -m src.gdes detect-cycles --json

Chain validation (directed path check):

    python -m src.gdes validate-chain <id1> <id2>
    python -m src.gdes validate-chain <id1> <id2> --json

Output includes: valid, path, hops, concepts_traversed.

Connected components:

    python -m src.gdes components
    python -m src.gdes components --json

Output: component count, node lists, largest first.

---

## Backup / Restore

    python -m src.gdes backup
    python -m src.gdes restore <backup_file>
    python -m src.gdes export-all

---

## Release Checkpoints

| Tag | Stable contract |
|-----|----------------|
| gdes-v1.8 | Filtered traversal CLI — --concept/--type on neighbors/subgraph/path |
| gdes-v1.9 | Advanced queries — detect-cycles, validate-chain, components |
