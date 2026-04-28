"""Test V1.10 concept inheritance resolver"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import yaml
from src.resolvers.concept_inheritance import (
    ConceptResolver,
    CycleError,
    MissingParentError,
    AbstractConceptError,
    InheritanceError,
    resolve_concept_paths,
)


@pytest.fixture
def resolver(tmp_path: Path):
    (tmp_path / "base.yaml").write_text("""
concept_id: base
identity:
  name: Base Concept
  type: System
purpose:
  solves: "Foundation for all concepts"
contract:
  allowed_types:
    - generic
responsibilities:
  - "Base responsibility"
boundaries:
  explicitly_forbidden:
    - "base_forbidden"
  drift_warnings:
    - "base_warning"
meta:
  extends: null
  abstract: true
  version: 1.10.0
""")

    (tmp_path / "finance.yaml").write_text("""
concept_id: finance
identity:
  name: Finance
  type: Business
purpose:
  solves: "Track financial documents"
contract:
  allowed_types:
    - invoice
    - receipt
responsibilities:
  - "Process financial documents"
  - "Validate amounts"
boundaries:
  explicitly_forbidden:
    - "personal_finance_tracking"
  drift_warnings:
    - "Do not add crypto trading"
meta:
  extends: base
  abstract: false
  version: 1.10.0
""")

    (tmp_path / "audit.yaml").write_text("""
concept_id: audit
identity:
  name: Audit
  type: Compliance
purpose:
  solves: "Audit financial records"
contract:
  allowed_types:
    - audit_report
responsibilities:
  - "Review financial docs"
boundaries:
  explicitly_forbidden:
    - "tamper_evidence"
meta:
  extends: finance
  abstract: false
  version: 1.10.0
""")

    return ConceptResolver([tmp_path], strict=True)


def test_loads_all_concepts(resolver: ConceptResolver):
    assert set(resolver.list_concepts()) == {"audit", "base", "finance"}


def test_finance_union_boundaries(resolver: ConceptResolver):
    schema = resolver.get_schema("finance")
    forbidden = schema["boundaries"]["explicitly_forbidden"]
    assert "base_forbidden" in forbidden
    assert "personal_finance_tracking" in forbidden


def test_finance_union_responsibilities(resolver: ConceptResolver):
    schema = resolver.get_schema("finance")
    resp = schema["responsibilities"]
    assert "Base responsibility" in resp
    assert "Process financial documents" in resp


def test_audit_deep_lineage(resolver: ConceptResolver):
    schema = resolver.get_schema("audit")
    resp = schema["responsibilities"]
    assert "Base responsibility" in resp
    assert "Process financial documents" in resp
    assert "Review financial docs" in resp


def test_meta_cleaned(resolver: ConceptResolver):
    schema = resolver.get_schema("finance")
    meta = schema["meta"]
    assert "extends" not in meta
    assert meta["resolved"] is True
    assert meta["resolved_version"] == "1.10.0"


def test_lineage_two_level(resolver: ConceptResolver):
    assert resolver.get_lineage("finance") == ["base", "finance"]


def test_lineage_three_level(resolver: ConceptResolver):
    assert resolver.get_lineage("audit") == ["base", "finance", "audit"]


def test_abstract_base_cannot_instantiate(resolver: ConceptResolver):
    with pytest.raises(AbstractConceptError):
        resolver.get_schema("base")


def test_cycle_detection(tmp_path: Path):
    (tmp_path / "a.yaml").write_text("concept_id: a\nmeta:\n  extends: b\n")
    (tmp_path / "b.yaml").write_text("concept_id: b\nmeta:\n  extends: a\n")
    with pytest.raises(CycleError):
        ConceptResolver([tmp_path])


def test_missing_parent(tmp_path: Path):
    (tmp_path / "child.yaml").write_text("concept_id: child\nmeta:\n  extends: ghost\n")
    with pytest.raises(MissingParentError):
        ConceptResolver([tmp_path])


def test_unknown_concept(resolver: ConceptResolver):
    with pytest.raises(InheritanceError):
        resolver.get_schema("ghost")


def test_root_level_extends_fallback(tmp_path: Path):
    (tmp_path / "parent.yaml").write_text("concept_id: parent\nextends: null\n")
    (tmp_path / "child.yaml").write_text("concept_id: child\nextends: parent\n")
    r = ConceptResolver([tmp_path])
    assert r.get_lineage("child") == ["parent", "child"]


def test_resolve_concept_paths_returns_list():
    paths = resolve_concept_paths()
    assert isinstance(paths, list)
    assert all(isinstance(p, Path) for p in paths)
