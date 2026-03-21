# GDES MVP — Proven Usage

## Concept File Location Priority

GDES resolves concepts in this order (first match wins):

1. **Project-local**: `./concepts/{concept_id}.yaml`
2. **Configured path**: (if set in config)
3. **User home**: `~/.gdes/concepts/{concept_id}.yaml`

Run from your project root to use local concepts.

## Supported Workflow

Create artifact:
    echo "def func(): pass" | python -m gdes pipeline --stdin -c my_tool -t code

## Failure Behavior

Missing concept: Clean error, paths shown, no traceback.
Wrong type: Rejected at Stage B, rolled back automatically.

## Rollback Behavior

Failed runs clean up automatically.
Verify: python -m gdes status (partials == canonicals == reports)

## Retrieval Usage

List by concept:
    python -m gdes search --concept my_tool --json

Check health:
    python -m gdes status
