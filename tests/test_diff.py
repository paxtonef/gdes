"""Test V1.17 artifact diff"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.diff import ArtifactDiff, DiffResult
from src.core import Config


def test_diff_identical_artifacts_raises_for_same_id():
    cfg = Config()
    differ = ArtifactDiff(cfg)
    # Same ID should find the same artifact — technically identical
    # But we need two different IDs in the registry to test
    all_ids = [a.id for a in differ.registry.search_all()]
    if len(all_ids) < 2:
        pytest.skip("Need at least 2 artifacts in registry")
    result = differ.diff(all_ids[0], all_ids[0])
    assert result.identical is True


def test_diff_result_dict():
    result = DiffResult(identical=False, content_diff=["-old", "+new"])
    d = result.to_dict()
    assert d["identical"] is False
    assert d["content_changed"] is True


def test_diff_unknown_artifact_raises():
    cfg = Config()
    differ = ArtifactDiff(cfg)
    with pytest.raises(ValueError):
        differ.diff("does-not-exist-000", "also-fake-000")
