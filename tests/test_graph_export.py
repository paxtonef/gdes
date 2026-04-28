"""Test V1.16 graph export"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.exporters.graph_export import GraphExporter
from src.core import Config


def test_exporter_builds_edges():
    cfg = Config()
    exporter = GraphExporter(cfg)
    edges = exporter.build_edges()
    assert isinstance(edges, list)
    for e in edges:
        assert len(e) == 3
        assert isinstance(e[0], str)
        assert isinstance(e[1], str)


def test_mermaid_output_contains_flowchart():
    cfg = Config()
    exporter = GraphExporter(cfg)
    edges = exporter.build_edges()
    mmd = exporter.to_mermaid(edges)
    assert mmd.startswith('flowchart TD')
    if edges:
        assert '-->' in mmd


def test_dot_output_contains_digraph():
    cfg = Config()
    exporter = GraphExporter(cfg)
    edges = exporter.build_edges()
    dot = exporter.to_dot(edges)
    assert dot.startswith('digraph G {')
    assert 'rankdir=LR;' in dot
    if edges:
        assert '->' in dot


def test_export_to_file(tmp_path: Path):
    cfg = Config()
    exporter = GraphExporter(cfg)
    out = tmp_path / 'graph.md'
    exporter.export(format='mermaid', output=out)
    assert out.exists()
    assert out.read_text().startswith('flowchart TD')


def test_export_unknown_format_raises():
    cfg = Config()
    exporter = GraphExporter(cfg)
    with pytest.raises(ValueError):
        exporter.export(format='xml')
