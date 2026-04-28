"""Test V1.14 concept schema migration"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.migration import SchemaMigration, MigrationReport
from src.core import Config
from src.concept_d import Registry


def test_migration_reports_shape():
    cfg = Config()
    report = SchemaMigration(cfg).run(apply=False)
    assert isinstance(report, MigrationReport)
    assert report.total >= 0
    assert report.passed + report.failed + report.skipped == report.total


def test_migration_dry_run_does_not_modify_db():
    cfg = Config()
    before = Registry(cfg).total_count()
    report = SchemaMigration(cfg).run(apply=False)
    assert Registry(cfg).total_count() == before


def test_migration_detects_abstract_concept():
    cfg = Config()
    with pytest.raises(Exception):
        SchemaMigration(cfg).resolver.get_schema("base")


def test_migration_report_dict():
    report = MigrationReport(total=5, passed=3, failed=1, skipped=1)
    d = report.to_dict()
    assert d["total"] == 5
    assert d["passed"] == 3
    assert "drift" in d
