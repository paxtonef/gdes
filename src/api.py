"""
GDES V2.0 — REST API Facade
Exposes existing CLI engine via HTTP. No logic lives here — routes delegate
to the same core used by the CLI.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .core import Config
from .concept_a import Ingestor
from .concept_b import Librarian, ConceptValidationError
from .concept_c import Validator
from .concept_d import Registry
from .artifact import CanonicalArtifact, PartialArtifact
from .graph import (
    build_adjacency, neighbors, subgraph, shortest_path,
    detect_cycles, validate_chain, connected_components,
)
from .health.integrity import IntegrityChecker

app = FastAPI(
    title="GDES API",
    description="Graph-Driven Engineering System — REST facade over the GDES core engine.",
    version="2.0.0",
)

# ── helpers ───────────────────────────────────────────────────────────────────

def _cfg() -> Config:
    return Config()

def _db_path() -> Path:
    cfg = _cfg()
    return Path(cfg.paths.output) / "registry.db"

def _get_artifacts():
    """Load all artifacts from registry as list of dicts for graph functions."""
    db = _db_path()
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, concept, type, metadata_json FROM artifacts")
    rows = cur.fetchall()
    conn.close()
    result = []
    for row in rows:
        meta = json.loads(row["metadata_json"] or "{}")
        result.append({
            "id": row["id"],
            "concept": row["concept"],
            "type": row["type"],
            "related_to": meta.get("related_to", []),
        })
    return result

def _require_node(graph, node_id, label="node"):
    if node_id not in graph:
        raise HTTPException(status_code=404, detail=f"{label} {node_id!r} not found")

# ── models ────────────────────────────────────────────────────────────────────

class PipelineRequest(BaseModel):
    content: str
    concept: str
    type: str
    source: str = "api"

class LinkRequest(BaseModel):
    artifact_id: str
    related_id: str

# ── health / status ───────────────────────────────────────────────────────────

@app.get("/health", tags=["system"])
def get_health():
    """Graph integrity and operational health."""
    db = _db_path()
    if not db.exists():
        raise HTTPException(status_code=503, detail="registry database not found")
    checker = IntegrityChecker(db)
    report = checker.check()
    from dataclasses import asdict
    return asdict(report)


@app.get("/status", tags=["system"])
def get_status():
    """Registry artifact counts."""
    db = _db_path()
    if not db.exists():
        raise HTTPException(status_code=503, detail="registry database not found")
    conn = sqlite3.connect(str(db))
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM artifacts")
    total = cur.fetchone()[0]
    cur.execute("SELECT concept, COUNT(*) as n FROM artifacts GROUP BY concept")
    by_concept = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return {"total": total, "by_concept": by_concept}


# ── search ────────────────────────────────────────────────────────────────────

@app.get("/search", tags=["query"])
def search(
    concept: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
    related_to: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Search artifacts by concept, type, or relationship."""
    db = _db_path()
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    sql = "SELECT id, concept, type, source, created_at, metadata_json FROM artifacts WHERE 1=1"
    params = []
    if concept:
        sql += " AND concept = ?"
        params.append(concept)
    if type:
        sql += " AND type = ?"
        params.append(type)
    sql += f" ORDER BY created_at DESC LIMIT {limit}"

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()

    results = []
    for row in rows:
        meta = json.loads(row["metadata_json"] or "{}")
        if related_to and related_to not in meta.get("related_to", []):
            continue
        results.append({
            "id": row["id"],
            "concept": row["concept"],
            "type": row["type"],
            "source": row["source"],
            "created_at": row["created_at"],
            "related_to": meta.get("related_to", []),
        })
    return {"ok": True, "count": len(results), "results": results}


# ── pipeline ──────────────────────────────────────────────────────────────────

@app.post("/pipeline", tags=["pipeline"])
def run_pipeline(req: PipelineRequest):
    """Ingest content through the full A→B→C→D pipeline."""
    cfg = _cfg()

    # Write content to a temp file (pipeline expects a file path)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(req.content)
        tmp_path = Path(f.name)

    try:
        # Stage A — ingest
        ingestor = Ingestor(cfg)
        partial = ingestor.ingest_file(tmp_path, source=req.source)

        # Stage B — tag/validate concept
        librarian = Librarian(cfg)
        canonical = librarian.tag(partial, concept=req.concept, type_=req.type)

        # Stage C — validate
        validator = Validator(cfg)
        report = validator.validate(canonical)
        if report.result != "pass":
            return JSONResponse(
                status_code=422,
                content={"ok": False, "stage": "C", "violations": report.violations},
            )

        # Stage D — store
        registry = Registry(cfg)
        registry.store(canonical)

        return {
            "ok": True,
            "id": canonical.id,
            "concept": req.concept,
            "type": req.type,
        }
    except ConceptValidationError as e:
        return JSONResponse(status_code=422, content={"ok": False, "error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
    finally:
        tmp_path.unlink(missing_ok=True)


# ── links ─────────────────────────────────────────────────────────────────────

@app.post("/link", tags=["links"])
def link_artifacts(req: LinkRequest):
    """Add a directed reference from artifact_id to related_id."""
    from .linking import add_reference, validate_references
    db = _db_path()
    try:
        add_reference(db, req.artifact_id, req.related_id)
        return {"ok": True, "artifact_id": req.artifact_id, "related_id": req.related_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/refs/{artifact_id}", tags=["links"])
def get_refs(artifact_id: str):
    """Get all artifacts that reference the given artifact."""
    from .linking import get_links
    db = _db_path()
    try:
        links = get_links(db, artifact_id)
        return {"ok": True, "artifact_id": artifact_id, "refs": links}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── graph traversal ───────────────────────────────────────────────────────────

@app.get("/neighbors/{artifact_id}", tags=["graph"])
def get_neighbors(
    artifact_id: str,
    concept: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
):
    """Get direct neighbors of an artifact, optionally filtered."""
    artifacts = _get_artifacts()
    graph, meta = build_adjacency(artifacts)
    _require_node(graph, artifact_id)
    result = neighbors(graph, meta, artifact_id, concept=concept, type_=type)
    return {"ok": True, "artifact_id": artifact_id, "neighbors": result,
            "filters": {"concept": concept, "type": type}}


@app.get("/subgraph/{artifact_id}", tags=["graph"])
def get_subgraph(
    artifact_id: str,
    depth: int = Query(1, ge=1, le=10),
    concept: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
):
    """BFS subgraph from artifact, optionally filtered."""
    artifacts = _get_artifacts()
    graph, meta = build_adjacency(artifacts)
    _require_node(graph, artifact_id)
    result = subgraph(graph, meta, artifact_id, depth=depth, concept=concept, type_=type)
    return {"ok": True, "artifact_id": artifact_id, "depth": depth,
            "nodes": result, "filters": {"concept": concept, "type": type}}


@app.get("/path", tags=["graph"])
def get_path(
    src: str = Query(...),
    dst: str = Query(...),
    concept: Optional[str] = Query(None),
    type: Optional[str] = Query(None, alias="type"),
):
    """Find shortest path between two artifacts, optionally filtered."""
    artifacts = _get_artifacts()
    graph, meta = build_adjacency(artifacts)
    _require_node(graph, src, "source")
    _require_node(graph, dst, "destination")
    result = shortest_path(graph, meta, src, dst, concept=concept, type_=type)
    return {"ok": True, "src": src, "dst": dst, "path": result,
            "filters": {"concept": concept, "type": type}}


# ── analysis ──────────────────────────────────────────────────────────────────

@app.get("/detect-cycles", tags=["analysis"])
def get_cycles():
    """Detect cycles in the artifact graph."""
    artifacts = _get_artifacts()
    graph, meta = build_adjacency(artifacts)
    cycles = detect_cycles(graph)
    return {"ok": True, "is_dag": len(cycles) == 0,
            "cycle_count": len(cycles), "cycles": cycles}


@app.get("/components", tags=["analysis"])
def get_components():
    """Show weakly connected components, largest first."""
    artifacts = _get_artifacts()
    graph, meta = build_adjacency(artifacts)
    comps = connected_components(graph)
    return {
        "ok": True,
        "component_count": len(comps),
        "components": [{"size": len(c), "nodes": c} for c in comps],
    }


@app.get("/validate-chain", tags=["analysis"])
def get_validate_chain(
    src: str = Query(...),
    dst: str = Query(...),
):
    """Validate that a directed path exists between two artifacts."""
    artifacts = _get_artifacts()
    graph, meta = build_adjacency(artifacts)
    result = validate_chain(graph, meta, src, dst)
    result["ok"] = True
    return result


# ── persistence ───────────────────────────────────────────────────────────────

@app.post("/backup", tags=["persistence"])
def do_backup():
    """Create a full system snapshot."""
    import shutil, time
    cfg = _cfg()
    output_dir = Path(cfg.paths.output)
    ts = int(time.time())
    backup_path = output_dir / f"registry_backup_{ts}.db"
    db = _db_path()
    if not db.exists():
        raise HTTPException(status_code=404, detail="registry not found")
    shutil.copy2(db, backup_path)
    return {"ok": True, "backup": str(backup_path)}
