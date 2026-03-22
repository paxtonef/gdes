"""
V1.8 tests: filtered graph traversal
"""
import pytest
from src.graph import build_adjacency, neighbors, subgraph, shortest_path


@pytest.fixture
def sample_artifacts():
    return [
        {"id": "1", "concept": "finance",   "type": "invoice",  "related_to": ["2", "3"]},
        {"id": "2", "concept": "finance",   "type": "invoice",  "related_to": ["4"]},
        {"id": "3", "concept": "security",  "type": "alert",    "related_to": []},
        {"id": "4", "concept": "config",    "type": "yaml",     "related_to": []},
        {"id": "5", "concept": "security",  "type": "alert",    "related_to": ["3"]},
    ]


@pytest.fixture
def graph_and_meta(sample_artifacts):
    return build_adjacency(sample_artifacts)


# ── neighbors ─────────────────────────────────────────────────────────────────

def test_neighbors_no_filter(graph_and_meta):
    g, m = graph_and_meta
    result = neighbors(g, m, "1")
    assert set(result) == {"2", "3"}


def test_neighbors_filter_by_concept(graph_and_meta):
    g, m = graph_and_meta
    result = neighbors(g, m, "1", concept="finance")
    assert result == ["2"]       # "3" is security, excluded


def test_neighbors_filter_by_type(graph_and_meta):
    g, m = graph_and_meta
    result = neighbors(g, m, "1", type_="alert")
    assert result == ["3"]       # "2" is invoice, excluded


def test_neighbors_no_match(graph_and_meta):
    g, m = graph_and_meta
    result = neighbors(g, m, "1", concept="does_not_exist")
    assert result == []


def test_neighbors_invalid_node(graph_and_meta):
    g, m = graph_and_meta
    with pytest.raises(ValueError):
        neighbors(g, m, "999")


# ── subgraph ──────────────────────────────────────────────────────────────────

def test_subgraph_no_filter(graph_and_meta):
    g, m = graph_and_meta
    result = subgraph(g, m, "1", depth=1)
    assert set(result) == {"1", "2", "3"}


def test_subgraph_filter_by_concept(graph_and_meta):
    g, m = graph_and_meta
    result = subgraph(g, m, "1", depth=2, concept="finance")
    # start node always included; depth-1: "2" (finance ✓), "3" (security ✗)
    # depth-2: "4" (config ✗)
    assert "1" in result
    assert "2" in result
    assert "3" not in result
    assert "4" not in result


def test_subgraph_filter_by_type(graph_and_meta):
    g, m = graph_and_meta
    result = subgraph(g, m, "1", depth=1, type_="alert")
    assert "1" in result        # start always included
    assert "3" in result        # alert ✓
    assert "2" not in result    # invoice ✗


def test_subgraph_invalid_node(graph_and_meta):
    g, m = graph_and_meta
    with pytest.raises(ValueError):
        subgraph(g, m, "999", depth=2)


# ── shortest_path ─────────────────────────────────────────────────────────────

def test_path_no_filter(graph_and_meta):
    g, m = graph_and_meta
    result = shortest_path(g, m, "1", "4")
    assert result == ["1", "2", "4"]


def test_path_filter_by_concept_blocks_route(graph_and_meta):
    g, m = graph_and_meta
    # "4" is config, so filtering to finance means dst fails filter -> no path
    result = shortest_path(g, m, "1", "4", concept="finance")
    assert result == []


def test_path_filter_allows_route(graph_and_meta):
    g, m = graph_and_meta
    # both "2" and "4" reachable; but "4" is config so filtered out
    # direct finance path: 1->2 exists
    result = shortest_path(g, m, "1", "2", concept="finance")
    assert result == ["1", "2"]


def test_path_same_node(graph_and_meta):
    g, m = graph_and_meta
    result = shortest_path(g, m, "1", "1")
    assert result == ["1"]


def test_path_invalid_node(graph_and_meta):
    g, m = graph_and_meta
    with pytest.raises(ValueError):
        shortest_path(g, m, "1", "999")


def test_path_no_match_returns_empty(graph_and_meta):
    g, m = graph_and_meta
    result = shortest_path(g, m, "1", "3", concept="does_not_exist")
    assert result == []
