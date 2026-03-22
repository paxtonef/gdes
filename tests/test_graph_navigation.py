import json
import subprocess
import pytest
from pathlib import Path

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

@pytest.fixture(autouse=True)
def clean_staging():
    for d in ["partials", "canonical", "reports"]:
        p = Path.home() / ".gdes" / "inbox" / d
        if p.exists():
            for f in p.glob("*.json"):
                f.unlink()

def test_neighbors_valid():
    # Setup: create linked artifacts
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/linking/security_alert.txt --concept security --type incident_report")
    
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    sec = json.loads(run("python -m src.gdes search --concept security --json").stdout)[0]["id"]
    run(f"python -m src.gdes link {fin} {sec}")
    
    # Test neighbors
    res = run(f"python -m src.gdes neighbors {fin}")
    assert res.returncode == 0, f"neighbors failed: {res.stderr}"
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert isinstance(data["neighbors"], list)
    assert sec in data["neighbors"]

def test_neighbors_invalid():
    res = run("python -m src.gdes neighbors 999999-fake-id")
    assert res.returncode != 0

def test_subgraph_depth_1():
    # Setup
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/linking/security_alert.txt --concept security --type incident_report")
    
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    sec = json.loads(run("python -m src.gdes search --concept security --json").stdout)[0]["id"]
    run(f"python -m src.gdes link {fin} {sec}")
    
    # Test subgraph depth 1
    res = run(f"python -m src.gdes subgraph {fin} --depth 1")
    assert res.returncode == 0, f"subgraph failed: {res.stderr}"
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert isinstance(data["nodes"], list)
    assert fin in data["nodes"]
    assert sec in data["nodes"]

def test_subgraph_invalid():
    res = run("python -m src.gdes subgraph 999999-fake-id --depth 1")
    assert res.returncode != 0

def test_path_exists():
    # Setup linked chain: fin -> sec
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/linking/security_alert.txt --concept security --type incident_report")
    
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    sec = json.loads(run("python -m src.gdes search --concept security --json").stdout)[0]["id"]
    run(f"python -m src.gdes link {fin} {sec}")
    
    # Test path
    res = run(f"python -m src.gdes path {fin} {sec}")
    assert res.returncode == 0, f"path failed: {res.stderr}"
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert isinstance(data["path"], list)
    assert data["path"][0] == fin
    assert data["path"][-1] == sec

def test_path_no_route():
    # Two unlinked artifacts
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/linking/security_alert.txt --concept security --type incident_report")
    
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    sec = json.loads(run("python -m src.gdes search --concept security --json").stdout)[0]["id"]
    # Intentionally NOT linking them
    
    res = run(f"python -m src.gdes path {fin} {sec}")
    assert res.returncode != 0  # No path should fail

def test_path_same_node():
    # Create any artifact
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    
    res = run(f"python -m src.gdes path {fin} {fin}")
    assert res.returncode == 0, f"path same node failed: {res.stderr}"
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert data["path"] == [fin]
