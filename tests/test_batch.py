"""Test V1.13 batch pipeline"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.batch import BatchPipeline
from src.core import Config


@pytest.fixture
def batcher(tmp_path: Path):
    cfg = Config()
    (tmp_path / "a.txt").write_text("Valid invoice content")
    (tmp_path / "b.txt").write_text("Another valid content")
    (tmp_path / "bad.txt").write_text("password secret apikey")
    return cfg, tmp_path


def test_batch_processes_all_valid_files(batcher):
    cfg, tmp_path = batcher
    files = [tmp_path / "a.txt", tmp_path / "b.txt"]
    pipeline = BatchPipeline(cfg, "finance", "invoice", dry_run=True)
    result = pipeline.run(files)
    assert result.success_count == 2
    assert result.fail_count == 0
    assert result.error_count == 0


def test_batch_fails_forbidden_content(batcher):
    cfg, tmp_path = batcher
    files = [tmp_path / "bad.txt"]
    pipeline = BatchPipeline(cfg, "finance", "invoice", dry_run=True)
    result = pipeline.run(files)
    assert result.success_count == 0
    assert result.fail_count == 1
    assert result.failed[0]["stage"] == "C"


def test_batch_mixed_results(batcher):
    cfg, tmp_path = batcher
    files = [tmp_path / "a.txt", tmp_path / "bad.txt", tmp_path / "b.txt"]
    pipeline = BatchPipeline(cfg, "finance", "invoice", dry_run=True)
    result = pipeline.run(files)
    assert result.success_count == 2
    assert result.fail_count == 1
    assert result.error_count == 0


def test_batch_result_dict(batcher):
    cfg, tmp_path = batcher
    files = [tmp_path / "a.txt"]
    pipeline = BatchPipeline(cfg, "finance", "invoice", dry_run=True)
    result = pipeline.run(files)
    d = result.to_dict()
    assert d["total"] == 1
    assert d["success_count"] == 1
    assert "success" in d
