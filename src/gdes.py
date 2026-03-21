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
from .models import CanonicalArtifact, PartialArtifact, ValidationReport


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
@click.argument("concept", type=str, required=False)
def search(concept_opt: Optional[str], as_json: bool, search_all: bool, concept: Optional[str]) -> None:
    """Query SQLite for artifacts matching a concept."""

    chosen = concept_opt or concept
    
    cfg = Config()
    audit = AuditLogger(cfg)
    registry = Registry(cfg)
    
    if search_all:
        results = registry.search_all()
        search_target = "all"
    elif chosen:
        results = registry.search(chosen)
        search_target = chosen
    else:
        raise click.ClickException("Provide a concept or use --all")

    audit.log("search", {"concept": search_target, "count": len(results)})

    if as_json:
        click.echo(
            json.dumps([a.model_dump(mode="json") for a in results], ensure_ascii=False)
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


if __name__ == "__main__":
    cli()
