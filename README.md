# GDES v1.9

Local-first CLI for LLM artifact management with graph traversal and advanced queries.

## Quick Start

```bash
# Ingest an artifact
python -m src.gdes pipeline --file myfile.yaml --concept config --type yaml

# Check system health
python -m src.gdes health

# Explore the graph
python -m src.gdes neighbors <id>
python -m src.gdes subgraph <id> --depth 2
python -m src.gdes path <id1> <id2>
```

## Version History

| Tag | Feature |
|-----|---------|
| v1.3 | Durable state — backup/restore roundtrip |
| v1.4 | Multi-concept validation — 6 concepts, type policy |
| v1.5 | Concept interaction — linking, bidirectional refs |
| v1.6 | Relationship integrity — validation, queryability |
| v1.7 | Graph navigation — traversal, pathfinding |
| v1.7.1 | Operational hardening — health check, schema alignment |
| v1.8 | Filtered traversal — --concept and --type on all graph commands |
| v1.9 | Advanced queries — cycle detection, chain validation, components |

## Test Coverage

58 tests passing across all versions.
