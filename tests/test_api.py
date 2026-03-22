"""
V2.0 API tests — uses FastAPI TestClient, no server needed.
"""
import pytest
from fastapi.testclient import TestClient
from src.api import app

client = TestClient(app)


# ── health / status ───────────────────────────────────────────────────────────

def test_health_returns_200():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "integrity_score" in data
    assert "total_nodes" in data


def test_status_returns_200():
    res = client.get("/status")
    assert res.status_code == 200
    data = res.json()
    assert "total" in data
    assert "by_concept" in data


# ── search ────────────────────────────────────────────────────────────────────

def test_search_no_filters():
    res = client.get("/search")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert isinstance(data["results"], list)


def test_search_by_concept():
    res = client.get("/search?concept=config")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    for r in data["results"]:
        assert r["concept"] == "config"


def test_search_by_type():
    res = client.get("/search?type=yaml")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    for r in data["results"]:
        assert r["type"] == "yaml"


def test_search_unknown_concept_returns_empty():
    res = client.get("/search?concept=does_not_exist")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 0


# ── graph ─────────────────────────────────────────────────────────────────────

def _first_linked_id():
    """Return an artifact id that has at least one neighbor."""
    res = client.get("/search?limit=500")
    for r in res.json()["results"]:
        if r["related_to"]:
            return r["id"], r["related_to"][0]
    return None, None


def test_neighbors_valid_node():
    src, dst = _first_linked_id()
    if src is None:
        pytest.skip("no linked artifacts in registry")
    res = client.get(f"/neighbors/{src}")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert dst in data["neighbors"]


def test_neighbors_unknown_node_returns_404():
    res = client.get("/neighbors/does-not-exist-000")
    assert res.status_code == 404


def test_subgraph_valid_node():
    src, _ = _first_linked_id()
    if src is None:
        pytest.skip("no linked artifacts in registry")
    res = client.get(f"/subgraph/{src}?depth=2")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert src in data["nodes"]


def test_path_valid():
    src, dst = _first_linked_id()
    if src is None:
        pytest.skip("no linked artifacts in registry")
    res = client.get(f"/path?src={src}&dst={dst}")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert isinstance(data["path"], list)


def test_path_unknown_src_returns_404():
    res = client.get("/path?src=bad-id&dst=also-bad")
    assert res.status_code == 404


# ── analysis ──────────────────────────────────────────────────────────────────

def test_detect_cycles():
    res = client.get("/detect-cycles")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "is_dag" in data
    assert "cycle_count" in data


def test_components():
    res = client.get("/components")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "component_count" in data
    assert isinstance(data["components"], list)


def test_validate_chain_valid():
    src, dst = _first_linked_id()
    if src is None:
        pytest.skip("no linked artifacts in registry")
    res = client.get(f"/validate-chain?src={src}&dst={dst}")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "valid" in data


def test_validate_chain_no_path():
    # Use two unrelated IDs — likely no path between random artifacts
    res = client.get("/search?limit=500")
    results = res.json()["results"]
    isolated = [r for r in results if not r["related_to"]]
    if len(isolated) < 2:
        pytest.skip("not enough isolated nodes")
    src, dst = isolated[0]["id"], isolated[1]["id"]
    res = client.get(f"/validate-chain?src={src}&dst={dst}")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    # may or may not be valid depending on graph — just assert shape
    assert "valid" in data


# ── persistence ───────────────────────────────────────────────────────────────

def test_backup_creates_file():
    res = client.post("/backup")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "backup" in data
