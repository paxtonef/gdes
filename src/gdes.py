from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, Type, TypeVar

import click
import sys

from .concept_a import Ingestor
from .concept_b import Librarian, ConceptValidationError
from .concept_c import Validator
from .concept_d import Registry
from .core import AuditLogger, Config
from .artifact import CanonicalArtifact, PartialArtifact, ValidationReport
from .validators.relationship_schema import RelationshipValidator
from .persistence.staging_lock import staging_lock, StagingConcurrencyError


T = TypeVar("T")


def _abbr(s: str, n: int = 8) -> str:
    if len(s) <= n:
        return s
    return f"{s[:n]}..."


def _ensure_inbox_layout(cfg: Config) -> dict:
    cfg.ensure_dirs()
    partials = cfg.paths.inbox / "partials"
    canonical = cfg.paths.inbox / "canonical"
    reports = cfg.paths.inbox / "reports"

    partials.mkdir(parents=True, exist_ok=True)
    canonical.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    return {"partials": partials, "canonical": canonical, "reports": reports}


def _save_model_json(path: Path, model) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(), encoding="utf-8")


def _load_model_json(path: Path, cls: Type[T]) -> T:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    return cls.model_validate(data)  # type: ignore[return-value]


def _latest_file(folder: Path, suffix: str = ".json") -> Optional[Path]:
    if not folder.exists():
        return None
    candidates = [p for p in folder.glob(f"*{suffix}") if p.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _get_file_by_id(folder: Path, artifact_id: str) -> Path:
    p = folder / f"{artifact_id}.json"
    if not p.exists():
        raise FileNotFoundError(f"No staged file for artifact id {artifact_id} in {folder}")
    return p


def _read_content(file: Optional[Path]) -> str:
    if file is None:
        return click.get_text_stream("stdin").read()
    return file.read_text(encoding="utf-8")


@click.group()
def cli() -> None:
    """GDES: a small artifact ingestion/tagging/validation/registry CLI."""


@cli.command()
@click.option("--file", "file_", type=click.Path(path_type=Path, dir_okay=False), required=False)
@click.option("--source", type=str, required=False, default=None)
def ingest(file_: Optional[Path], source: Optional[str]) -> None:
    """Reads a file or stdin and saves a PartialArtifact to staging."""

    cfg = Config()
    audit = AuditLogger(cfg)
    layout = _ensure_inbox_layout(cfg)

    content = _read_content(file_)
    src = source or (str(file_) if file_ else "stdin")

    artifact = Ingestor().ingest(content=content, source=src)
    out_path = layout["partials"] / f"{artifact.id}.json"
    _save_model_json(out_path, artifact)

    audit.log("ingest", {"artifact_id": artifact.id, "source": src, "path": str(out_path)})
    click.echo(artifact.id)


@cli.command()
@click.option("--artifact-id", type=str, required=False, default=None)
def tag(artifact_id: Optional[str]) -> None:
    """Asks for concept and type, loads a staged PartialArtifact, and stages a CanonicalArtifact."""

    cfg = Config()
    audit = AuditLogger(cfg)
    layout = _ensure_inbox_layout(cfg)

    partial_path = (
        _get_file_by_id(layout["partials"], artifact_id)
        if artifact_id
        else _latest_file(layout["partials"])
    )
    if partial_path is None:
        raise click.ClickException(f"No staged partial artifacts found in {layout['partials']}")

    partial = _load_model_json(partial_path, PartialArtifact)

    concept_name = click.prompt("Concept", type=str)
    artifact_type = click.prompt(
        "Type",
        type=str,  # Concept-driven: validated at Stage B,
    )

    librarian = Librarian(cfg)
    canonical = librarian.tag(partial=partial, concept_name=concept_name, artifact_type=artifact_type)

    out_path = layout["canonical"] / f"{canonical.id}.json"
    _save_model_json(out_path, canonical)

    audit.log(
        "tag",
        {
            "artifact_id": canonical.id,
            "concept": canonical.concept,
            "type": canonical.artifact_type,
            "in_path": str(partial_path),
            "out_path": str(out_path),
        },
    )
    click.echo(canonical.id)


@cli.command()
@click.option("--artifact-id", type=str, required=False, default=None)
def validate(artifact_id: Optional[str]) -> None:
    """Runs validator on a staged CanonicalArtifact and stages a ValidationReport."""

    cfg = Config()
    audit = AuditLogger(cfg)
    layout = _ensure_inbox_layout(cfg)

    canonical_path = (
        _get_file_by_id(layout["canonical"], artifact_id)
        if artifact_id
        else _latest_file(layout["canonical"])
    )
    if canonical_path is None:
        raise click.ClickException(f"No staged canonical artifacts found in {layout['canonical']}")

    canonical = _load_model_json(canonical_path, CanonicalArtifact)

    validator = Validator(cfg)
    report = validator.validate(canonical)

    out_path = layout["reports"] / f"{report.artifact_id}.json"
    _save_model_json(out_path, report)

    audit.log(
        "validate",
        {
            "artifact_id": report.artifact_id,
            "concept": report.concept,
            "result": report.result,
            "in_path": str(canonical_path),
            "out_path": str(out_path),
        },
    )

    click.echo(report.result)
    if report.result != "pass":
        for v in report.violations:
            click.echo(v)


@cli.command()
@click.option("--artifact-id", type=str, required=False, default=None)
def store(artifact_id: Optional[str]) -> None:
    """Moves staged canonical artifact to SQLite registry if report passed."""

    cfg = Config()
    audit = AuditLogger(cfg)
    layout = _ensure_inbox_layout(cfg)

    canonical_path = (
        _get_file_by_id(layout["canonical"], artifact_id)
        if artifact_id
        else _latest_file(layout["canonical"])
    )
    if canonical_path is None:
        raise click.ClickException(f"No staged canonical artifacts found in {layout['canonical']}")

    canonical = _load_model_json(canonical_path, CanonicalArtifact)
    report_path = _get_file_by_id(layout["reports"], canonical.id)
    report = _load_model_json(report_path, ValidationReport)

    registry = Registry(cfg)
    registry.store(canonical, report)

    audit.log(
        "store",
        {
            "artifact_id": canonical.id,
            "concept": canonical.concept,
            "db": str(cfg.paths.output / "registry.db"),
        },
    )
    click.echo(canonical.id)


@cli.command()
@click.option("--file", "file_", type=click.Path(path_type=Path, dir_okay=False), required=False)
@click.option("--stdin", "stdin_", is_flag=True, default=False)
@click.option("--source", type=str, required=False, default=None)
@click.option("-c", "--concept", "concept_name", type=str, required=False, default=None)
@click.option(
    "-t",
    "--type",
    "artifact_type",
    type=str,  # Concept-driven: validated at Stage B,
    required=False,
    default=None,
)
def pipeline(
    file_: Optional[Path],
    stdin_: bool,
    source: Optional[str],
    concept_name: Optional[str],
    artifact_type: Optional[str],
) -> None:
    """Runs A→B→C→D in one go."""

    start = time.perf_counter()
    click.echo("🔄  GDES Pipeline: A→B→C→D")
    click.echo("")

    cfg = Config()
    audit = AuditLogger(cfg)
    layout = _ensure_inbox_layout(cfg)

    if stdin_ and file_ is not None:
        raise click.ClickException("Use either --stdin or --file, not both")

    if stdin_:
        content = click.get_text_stream("stdin").read()
        src = source or "stdin"
    else:
        content = _read_content(file_)
        src = source or (str(file_) if file_ else "stdin")

    partial = Ingestor().ingest(content=content, source=src)
    partial_path = layout["partials"] / f"{partial.id}.json"
    _save_model_json(partial_path, partial)

    click.echo(f"  ✅ A id={_abbr(partial.id)}")

    if concept_name is None:
        concept_name = click.prompt("Concept", type=str)
    if artifact_type is None:
        artifact_type = click.prompt(
            "Type",
            type=str,  # Concept-driven: validated at Stage B,
        )

    try:
        canonical = Librarian(cfg).tag(partial=partial, concept_name=concept_name, artifact_type=artifact_type)
    except ConceptValidationError as e:
        click.echo(f"  ❌ B concept validation failed")
        click.echo(f"\n{e}")
        # PRIORITY 2: Cleanup partial on failure
        partial_temp = layout["partials"] / f"{partial.id}.json"
        if partial_temp.exists():
            partial_temp.unlink()
            click.echo(f"  🧹 Rolled back: {partial_temp.name}")
        sys.exit(1)
    
    canonical_path = layout["canonical"] / f"{canonical.id}.json"
    _save_model_json(canonical_path, canonical)

    click.echo(f"  ✅ B c={canonical.concept} t={canonical.artifact_type}")

    report = Validator(cfg).validate(canonical)
    report_path = layout["reports"] / f"{report.artifact_id}.json"
    _save_model_json(report_path, report)

    checks_keys = "".join(k[:1] for k in report.checks.keys())
    click.echo(f"  ✅ C r={report.result} checks=[{','.join(checks_keys)}]")

    if report.result != "pass":
        audit.log(
            "pipeline_fail",
            {
                "artifact_id": report.artifact_id,
                "concept": report.concept,
                "result": report.result,
                "violations": report.violations,
            },
        )
        end = time.perf_counter()
        click.echo(report.result)
        for v in report.violations:
            click.echo(v)
        ms = int((end - start) * 1000)
        click.echo(f"\n❌  Pipeline failed  ({ms}ms)  artifact_id={report.artifact_id}")
        raise SystemExit(1)

    registry = Registry(cfg)
    registry.store(canonical, report)
    total = registry.total_count()
    orphans = registry.orphan_count()
    click.echo(f"  ✅ D stored total={total} orphan={orphans}")
    click.echo("")

    audit.log(
        "pipeline",
        {
            "artifact_id": canonical.id,
            "concept": canonical.concept,
            "type": canonical.artifact_type,
            "result": report.result,
        },
    )
    end = time.perf_counter()
    ms = int((end - start) * 1000)
    click.echo(f"✅ done {ms}ms id={_abbr(canonical.id)}")


@cli.command()
@click.option("--concept", "concept_opt", type=str, required=False, default=None)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.option("--all", "search_all", is_flag=True, help="Search across all concepts")
@click.option("--related-to", "related_to", type=str, required=False, help="Find artifacts referencing this ID")
@click.option("--relation", "relation_filter", type=str, required=False, help="Filter by relation type (e.g. audit, compliance)")
@click.argument("concept", type=str, required=False)
def search(concept_opt: Optional[str], as_json: bool, search_all: bool, concept: Optional[str], related_to: Optional[str] = None, relation_filter: Optional[str] = None) -> None:
    """Query SQLite for artifacts matching a concept."""

    chosen = concept_opt or concept
    
    cfg = Config()
    audit = AuditLogger(cfg)
    registry = Registry(cfg)
    
    if related_to:
        all_results = registry.search_all()
        results = [a for a in all_results if related_to in a.metadata.get("related_to", [])]
        search_target = f"related-to:{related_to}"
    elif search_all:
        results = registry.search_all()
        search_target = "all"
    elif chosen:
        results = registry.search(chosen)
        search_target = chosen
    else:
        raise click.ClickException("Provide a concept or use --all")

    audit.log("search", {"concept": search_target, "count": len(results)})

    if as_json:
        payload = []
        for a in results:
            d = a.model_dump(mode="json")
            if "artifact_type" in d and "type" not in d:
                d["type"] = d["artifact_type"]
            payload.append(d)
        click.echo(
            json.dumps(payload, ensure_ascii=False)
        )
        return

    for a in results:
        click.echo(a.model_dump_json())


@cli.command()
def status() -> None:
    """Shows counts for the registry and staging."""

    cfg = Config()
    _ensure_inbox_layout(cfg)

    registry = Registry(cfg)

    partials = list((cfg.paths.inbox / "partials").glob("*.json"))
    canonical = list((cfg.paths.inbox / "canonical").glob("*.json"))
    reports = list((cfg.paths.inbox / "reports").glob("*.json"))

    click.echo(f"Registry artifacts : {registry.total_count()}")
    click.echo(f"Orphan count : {registry.orphan_count()}")
    click.echo(f"Staging partials : {len(partials)}")
    click.echo(f"Staging canonical : {len(canonical)}")
    click.echo(f"Staging reports : {len(reports)}")




import json
import time
import shutil
from pathlib import Path

@cli.command()
@click.argument('export_file', type=click.Path(exists=True))
def rebuild_registry(export_file):
    """Rebuild SQLite registry from JSON export (destructive)"""
    from src.concept_d import Registry
    from src.core import Config
    from src.artifact import CanonicalArtifact, ValidationReport
    
    cfg = Config()
    registry = Registry(cfg)
    
    db_path = Path.home() / ".gdes" / "registry.db"
    if db_path.exists():
        backup_db = str(db_path) + f".archive_{int(time.time())}"
        shutil.copy(db_path, backup_db)
        click.echo(f"Archived current registry to {backup_db}")
    
    with open(export_file) as f:
        artifacts = json.load(f)
    
    if db_path.exists():
        db_path.unlink()
    
    registry = Registry(cfg)
    
    restored = 0
    for art_dict in artifacts:
        artifact = CanonicalArtifact(**art_dict)
        # Create synthetic pass report for restored artifact
        report = ValidationReport(
            artifact_id=artifact.id,
            concept=artifact.concept,
            result="pass",
            checks={"restored": True}
        )
        registry.store(artifact, report)
        restored += 1
    
    click.echo(f"Restored {restored} artifacts")

import os

@cli.command(name="backup")
def cli_backup():
    """Create full system snapshot"""
    script_path = Path(__file__).parent.parent / "scripts" / "backup.sh"
    os.system(f"bash {script_path}")

@cli.command(name="restore")
@click.argument("backup_file")
@click.option("--force", is_flag=True, help="Skip confirmation")
def cli_restore(backup_file, force):
    """Restore from snapshot (destructive)"""
    if not force:
        click.confirm(f"Replace current state with {backup_file}?", abort=True)
    script_path = Path(__file__).parent.parent / "scripts" / "restore.sh"
    os.system(f"bash {script_path} {backup_file}")

@cli.command(name="export-all")
@click.argument("output_file")
def cli_export_all(output_file):
    """Export entire registry to JSON"""
    os.system(f".venv/bin/python -m src.gdes search --all --json > {output_file}")
    click.echo(f"Exported to {output_file}")



@cli.command(name="link")
@click.argument("artifact_id")
@click.argument("related_id")
@click.option("--relation", default=None, help="Relation type (e.g. compliance, audit, depends_on)")
def link_artifacts(artifact_id, related_id, relation):
    """Add reference from artifact_id to related_id (V1.7.2 with concept-type validation)"""
    from src.concept_d import Registry
    from src.core import Config
    from src.linking import validate_references, get_links, add_reference
    import json
    
    cfg = Config()
    registry = Registry(cfg)
    
    # Find artifacts
    all_artifacts = registry.search_all()
    artifact = next((a for a in all_artifacts if a.id == artifact_id), None)
    if not artifact:
        raise click.ClickException(f"Artifact {artifact_id} not found")
    related = next((a for a in all_artifacts if a.id == related_id), None)
    if not related:
        raise click.ClickException(f"Related artifact {related_id} not found")
    
    # Concept-type relationship validation (V1.7.2 wiring)
    rel_validator = RelationshipValidator(strict=True)
    source_concept = artifact.concept
    target_concept = related.concept
    
    if relation is None:
        valid_targets = rel_validator.get_valid_targets(source_concept)
        if target_concept in valid_targets:
            relation = valid_targets[target_concept][0]
            click.echo(f"  ℹ️  Auto-selected relation: '{relation}'")
        else:
            raise click.ClickException(
                f"No schema defined for {source_concept} → {target_concept}. "
                f"Use --relation with an explicit type, or define the pair in RELATIONSHIP_SCHEMA."
            )
    
    try:
        rel_validator.validate(source_concept, target_concept, relation)
    except ValueError as e:
        raise click.ClickException(str(e))
    
    # Convert to dict for linking validation
    art_dict = _artifact_to_dict(artifact)
    
    # Check existing refs for duplicates
    existing_ids = {a.id for a in all_artifacts}
    
    # Validate before adding (self-link check)
    if artifact_id == related_id:
        raise click.ClickException("self-link is not allowed")
    
    # Check for duplicate
    if related_id in get_links(art_dict):
        raise click.ClickException("duplicate link is not allowed")
    
    # Add reference
    try:
        updated = add_reference(art_dict, related_id)
    except ValueError as e:
        raise click.ClickException(str(e))
    
    # Store updated refs + typed relation for V1.8+ traceability
    updated_meta = dict(artifact.metadata)
    updated_meta["related_to"] = updated.get("related_to", [])
    
    # Backward-compatible: relation_types is new, related_to stays flat for graph traversal
    if "relation_types" not in updated_meta:
        updated_meta["relation_types"] = {}
    updated_meta["relation_types"][related_id] = relation
    
    with registry._connect() as conn:
        conn.execute(
            "UPDATE artifacts SET metadata_json = ? WHERE id = ?",
            (json.dumps(updated_meta), artifact_id)
        )
        conn.commit()
    
    click.echo(f"Linked {artifact_id} → {related_id} ({relation})")

@cli.command(name="refs")
@click.argument("artifact_id")
def show_references(artifact_id):
    """Show artifacts related to given ID"""
    from src.concept_d import Registry
    from src.core import Config
    
    cfg = Config()
    registry = Registry(cfg)
    
    # Find artifact
    all_artifacts = registry.search_all()
    artifact = next((a for a in all_artifacts if a.id == artifact_id), None)
    if not artifact:
        raise click.ClickException(f"Artifact {artifact_id} not found")
    
    # Get refs from metadata
    related = artifact.metadata.get("related_to", [])
    
    click.echo(f"Artifact: {artifact_id}")
    click.echo(f"Concept: {artifact.concept}")
    click.echo(f"Type: {artifact.artifact_type}")
    click.echo(f"Related to: {related}")
    
    # Bidirectional: who references this
    referenced_by = [a.id for a in all_artifacts if artifact_id in a.metadata.get("related_to", [])]
    click.echo(f"Referenced by: {referenced_by}")



import json
from src.linking import validate_references, get_links, add_reference


def _artifact_to_dict(artifact):
    """Convert CanonicalArtifact to dict for linking.py"""
    return {
        "id": artifact.id,
        "concept": artifact.concept,
        "type": artifact.artifact_type,
        "content_hash": getattr(artifact, 'content_hash', ''),
        "created_at": str(artifact.created_at),
        "metadata": artifact.metadata,
        "related_to": artifact.metadata.get("related_to", [])
    }

def _dict_to_artifact_update(artifact_dict, original_artifact):
    """Update artifact metadata with new refs"""
    from src.artifact import ValidationReport
    from src.concept_d import Registry
    
    # Update metadata
    updated_meta = dict(original_artifact.metadata)
    updated_meta["related_to"] = artifact_dict.get("related_to", [])
    
    # Store update via registry
    cfg = Config()
    registry = Registry(cfg)
    
    with registry._connect() as conn:
        conn.execute(
            "UPDATE artifacts SET metadata_json = ? WHERE id = ?",
            (json.dumps(updated_meta), original_artifact.id)
        )
        conn.commit()

@cli.command(name="show-links")
@click.argument("artifact_id")
def show_links_cmd(artifact_id: str):
    """Show links for an artifact"""
    from src.concept_d import Registry
    from src.core import Config
    
    cfg = Config()
    registry = Registry(cfg)
    
    all_artifacts = registry.search_all()
    artifact = next((a for a in all_artifacts if a.id == artifact_id), None)
    
    if not artifact:
        click.echo(json.dumps({"ok": False, "error": "artifact not found"}))
        raise SystemExit(1)
    
    art_dict = _artifact_to_dict(artifact)
    links = get_links(art_dict)
    
    click.echo(json.dumps({
        "ok": True,
        "artifact_id": artifact_id,
        "concept": artifact.concept,
        "related_to": links,
    }, indent=2))

@cli.command(name="validate-links")
def validate_links_cmd():
    """Validate all references in registry"""
    from src.concept_d import Registry
    from src.core import Config
    
    cfg = Config()
    registry = Registry(cfg)
    
    all_artifacts = registry.search_all()
    existing_ids = {str(a.id) for a in all_artifacts}
    errors = []

    for artifact in all_artifacts:
        art_dict = _artifact_to_dict(artifact)
        artifact_errors = validate_references(art_dict, existing_ids)
        if artifact_errors:
            errors.append({
                "artifact_id": artifact.id,
                "errors": artifact_errors,
            })

    ok = len(errors) == 0
    click.echo(json.dumps({"ok": ok, "errors": errors}, indent=2))
    raise SystemExit(0 if ok else 1)

# Extend search command - need to add option to existing search



# V1.7: Graph Navigation Commands
from src.graph import build_adjacency, neighbors, subgraph, shortest_path, detect_cycles, validate_chain, connected_components

def _get_artifacts_for_graph():
    """Get all artifacts as dicts for graph operations"""
    from src.concept_d import Registry
    from src.core import Config
    
    cfg = Config()
    registry = Registry(cfg)
    
    all_artifacts = registry.search_all()
    result = []
    for a in all_artifacts:
        result.append({
            "id": a.id,
            "concept": a.concept,
            "type": a.artifact_type,
            "related_to": a.metadata.get("related_to", [])
        })
    return result

@cli.command(name="neighbors")
@click.argument("artifact_id")
@click.option("--concept", default=None, help="Filter neighbors by concept")
@click.option("--type", "type_", default=None, help="Filter neighbors by type")
def neighbors_cmd(artifact_id, concept, type_):
    """Get direct neighbors of an artifact, optionally filtered"""
    try:
        artifacts = _get_artifacts_for_graph()
        graph, meta = build_adjacency(artifacts)
        result = neighbors(graph, meta, artifact_id, concept=concept, type_=type_)
        click.echo(json.dumps({
            "ok": True,
            "artifact_id": artifact_id,
            "neighbors": result,
            "filters": {"concept": concept, "type": type_},
        }, indent=2))
    except Exception as e:
        click.echo(json.dumps({"ok": False, "error": str(e)}))
        raise SystemExit(1)

@cli.command(name="subgraph")
@click.argument("artifact_id")
@click.option("--depth", default=1, type=int, help="Traversal depth")
@click.option("--concept", default=None, help="Filter nodes by concept")
@click.option("--type", "type_", default=None, help="Filter nodes by type")
def subgraph_cmd(artifact_id, depth, concept, type_):
    """Get subgraph starting from artifact (BFS), optionally filtered"""
    try:
        artifacts = _get_artifacts_for_graph()
        graph, meta = build_adjacency(artifacts)
        result = subgraph(graph, meta, artifact_id, depth, concept=concept, type_=type_)
        click.echo(json.dumps({"ok": True, "start": artifact_id, "depth": depth, "nodes": result}, indent=2))
    except Exception as e:
        click.echo(json.dumps({"ok": False, "error": str(e)}))
        raise SystemExit(1)

@cli.command(name="path")
@click.argument("src")
@click.argument("dst")
@click.option("--concept", default=None, help="Only traverse nodes in this concept")
@click.option("--type", "type_", default=None, help="Only traverse nodes of this type")
def path_cmd(src, dst, concept, type_):
    """Find shortest path between two artifacts, optionally filtered"""
    try:
        artifacts = _get_artifacts_for_graph()
        graph, meta = build_adjacency(artifacts)
        result = shortest_path(graph, meta, src, dst, concept=concept, type_=type_)
        if not result:
            click.echo(json.dumps({"ok": False, "error": "no path found"}, indent=2))
            raise SystemExit(1)
        click.echo(json.dumps({"ok": True, "src": src, "dst": dst, "path": result}, indent=2))
    except Exception as e:
        click.echo(json.dumps({"ok": False, "error": str(e)}))
        raise SystemExit(1)




@cli.command(name="detect-cycles")
@click.option("--json", "output_json", is_flag=True, help="Output raw JSON")
def detect_cycles_cmd(output_json):
    """Detect cycles in the artifact graph"""
    try:
        artifacts = _get_artifacts_for_graph()
        graph, meta = build_adjacency(artifacts)
        cycles = detect_cycles(graph)
        result = {
            "ok": True,
            "cycle_count": len(cycles),
            "cycles": cycles,
            "is_dag": len(cycles) == 0,
        }
        if output_json:
            click.echo(json.dumps(result, indent=2))
        else:
            if result["is_dag"]:
                click.echo("✅ No cycles detected — graph is a DAG")
            else:
                click.echo(f"⚠  {result['cycle_count']} cycle(s) detected:")
                for i, cycle in enumerate(cycles, 1):
                    click.echo(f"  {i}. {' → '.join(cycle)}")
    except Exception as e:
        click.echo(json.dumps({"ok": False, "error": str(e)}))
        raise SystemExit(1)


@cli.command(name="validate-chain")
@click.argument("src")
@click.argument("dst")
@click.option("--json", "output_json", is_flag=True, help="Output raw JSON")
def validate_chain_cmd(src, dst, output_json):
    """Validate that a directed path exists between two artifacts"""
    try:
        artifacts = _get_artifacts_for_graph()
        graph, meta = build_adjacency(artifacts)
        result = validate_chain(graph, meta, src, dst)
        result["ok"] = True
        if output_json:
            click.echo(json.dumps(result, indent=2))
        else:
            if result["valid"]:
                path_str = " → ".join(result["path"])
                click.echo(f"✅ Valid chain ({result['hops']} hops): {path_str}")
                click.echo(f"   Concepts: {' → '.join(str(c) for c in result['concepts_traversed'])}")
            else:
                click.echo(f"❌ {result.get('error', 'no path found')}")
    except Exception as e:
        click.echo(json.dumps({"ok": False, "error": str(e)}))
        raise SystemExit(1)


@cli.command(name="components")
@click.option("--json", "output_json", is_flag=True, help="Output raw JSON")
def components_cmd(output_json):
    """Show weakly connected components of the artifact graph"""
    try:
        artifacts = _get_artifacts_for_graph()
        graph, meta = build_adjacency(artifacts)
        comps = connected_components(graph)
        result = {
            "ok": True,
            "component_count": len(comps),
            "components": [{"size": len(c), "nodes": c} for c in comps],
        }
        if output_json:
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Found {result['component_count']} component(s):")
            for i, comp in enumerate(result["components"], 1):
                click.echo(f"  {i}. size={comp['size']}  nodes={comp['nodes'][:5]}{'...' if comp['size'] > 5 else ''}")
    except Exception as e:
        click.echo(json.dumps({"ok": False, "error": str(e)}))
        raise SystemExit(1)

@cli.command(name="relations")
@click.argument("artifact_id")
def show_relations(artifact_id: str) -> None:
    """Show typed relations for an artifact."""
    from src.queries.relation_query import RelationQuery
    from src.core import Config

    cfg = Config()
    query = RelationQuery(cfg)
    rels = query.get_relations(artifact_id)
    incoming = query.get_incoming(artifact_id)

    if not rels and not incoming:
        click.echo(json.dumps({
            "ok": True,
            "artifact_id": artifact_id,
            "message": "No typed relations found",
            "outgoing": {},
            "incoming": [],
        }, indent=2))
        return

    click.echo(json.dumps({
        "ok": True,
        "artifact_id": artifact_id,
        "outgoing": rels,
        "incoming": [{"from": src, "relation": rel} for src, rel in incoming],
    }, indent=2))

if __name__ == "__main__":
    cli()
