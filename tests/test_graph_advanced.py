"""
V1.9 tests: cycle detection, chain validation, connected components
"""
import pytest
from src.graph import build_adjacency, detect_cycles, validate_chain, connected_components


@pytest.fixture
def dag_artifacts():
    """A clean DAG — no cycles"""
    return [
        {"id": "1", "concept": "finance",  "type": "invoice",  "related_to": ["2", "3"]},
        {"id": "2", "concept": "finance",  "type": "invoice",  "related_to": ["4"]},
        {"id": "3", "concept": "security", "type": "alert",    "related_to": ["4"]},
        {"id": "4", "concept": "config",   "type": "yaml",     "related_to": []},
        {"id": "5", "concept": "security", "type": "alert",    "related_to": []},
    ]


@pytest.fixture
def cyclic_artifacts():
    """Graph with a cycle: 1 → 2 → 3 → 1"""
    return [
        {"id": "1", "concept": "finance",  "type": "invoice",  "related_to": ["2"]},
        {"id": "2", "concept": "finance",  "type": "invoice",  "related_to": ["3"]},
        {"id": "3", "concept": "security", "type": "alert",    "related_to": ["1"]},
        {"id": "4", "concept": "config",   "type": "yaml",     "related_to": []},
    ]


@pytest.fixture
def dag_graph(dag_artifacts):
    return build_adjacency(dag_artifacts)


@pytest.fixture
def cyclic_graph(cyclic_artifacts):
    return build_adjacency(cyclic_artifacts)


# ── detect_cycles ─────────────────────────────────────────────────────────────

def test_no_cycles_in_dag(dag_graph):
    g, m = dag_graph
    assert detect_cycles(g) == []


def test_cycle_detected(cyclic_graph):
    g, m = cyclic_graph
    cycles = detect_cycles(g)
    assert len(cycles) >= 1
    # each cycle is a list of nodes forming a loop
    for cycle in cycles:
        assert isinstance(cycle, list)
        assert len(cycle) >= 2


def test_empty_graph_no_cycles():
    g, m = build_adjacency([])
    assert detect_cycles(g) == []


def test_self_loop_detected():
    artifacts = [{"id": "1", "concept": "finance", "type": "invoice", "related_to": ["1"]}]
    g, m = build_adjacency(artifacts)
    cycles = detect_cycles(g)
    assert len(cycles) >= 1


# ── validate_chain ────────────────────────────────────────────────────────────

def test_valid_chain_exists(dag_graph):
    g, m = dag_graph
    result = validate_chain(g, m, "1", "4")
    assert result["valid"] is True
    assert result["path"][0] == "1"
    assert result["path"][-1] == "4"
    assert result["hops"] >= 1
    assert isinstance(result["concepts_traversed"], list)


def test_chain_direct_hop(dag_graph):
    g, m = dag_graph
    result = validate_chain(g, m, "1", "2")
    assert result["valid"] is True
    assert result["hops"] == 1
    assert result["path"] == ["1", "2"]


def test_chain_no_path(dag_graph):
    g, m = dag_graph
    # "4" has no outgoing edges so no path from 4 to 1
    result = validate_chain(g, m, "4", "1")
    assert result["valid"] is False
    assert "path" in result


def test_chain_invalid_src(dag_graph):
    g, m = dag_graph
    result = validate_chain(g, m, "999", "1")
    assert result["valid"] is False
    assert "error" in result


def test_chain_invalid_dst(dag_graph):
    g, m = dag_graph
    result = validate_chain(g, m, "1", "999")
    assert result["valid"] is False
    assert "error" in result


def test_chain_concepts_traversed(dag_graph):
    g, m = dag_graph
    result = validate_chain(g, m, "1", "4")
    assert result["valid"] is True
    # concepts_traversed should have one entry per node in path
    assert len(result["concepts_traversed"]) == len(result["path"])


# ── connected_components ──────────────────────────────────────────────────────

def test_components_dag(dag_artifacts):
    """Node 5 is isolated, rest are connected — expect 2 components"""
    g, m = build_adjacency(dag_artifacts)
    comps = connected_components(g)
    assert len(comps) == 2
    sizes = [len(c) for c in comps]
    assert 4 in sizes  # main component: 1,2,3,4
    assert 1 in sizes  # isolated: 5


def test_components_all_connected():
    artifacts = [
        {"id": "1", "concept": "finance", "type": "invoice", "related_to": ["2"]},
        {"id": "2", "concept": "finance", "type": "invoice", "related_to": ["3"]},
        {"id": "3", "concept": "config",  "type": "yaml",    "related_to": []},
    ]
    g, m = build_adjacency(artifacts)
    comps = connected_components(g)
    assert len(comps) == 1
    assert len(comps[0]) == 3


def test_components_all_isolated():
    artifacts = [
        {"id": "1", "concept": "finance", "type": "invoice", "related_to": []},
        {"id": "2", "concept": "finance", "type": "invoice", "related_to": []},
        {"id": "3", "concept": "config",  "type": "yaml",    "related_to": []},
    ]
    g, m = build_adjacency(artifacts)
    comps = connected_components(g)
    assert len(comps) == 3
    assert all(len(c) == 1 for c in comps)


def test_components_largest_first(dag_artifacts):
    g, m = build_adjacency(dag_artifacts)
    comps = connected_components(g)
    sizes = [len(c) for c in comps]
    assert sizes == sorted(sizes, reverse=True)


def test_components_empty_graph():
    g, m = build_adjacency([])
    comps = connected_components(g)
    assert comps == []
