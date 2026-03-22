import subprocess
import json

def run(cmd: str):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def test_duplicate_link_rejected():
    # First link should work
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/linking/security_alert.txt --concept security --type incident_report")
    
    # Get IDs
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    sec = json.loads(run("python -m src.gdes search --concept security --json").stdout)[0]["id"]
    
    # Link once
    run(f"python -m src.gdes link {fin} {sec}")
    # Duplicate should fail
    res = run(f"python -m src.gdes link {fin} {sec}")
    assert res.returncode != 0 or "duplicate" in (res.stdout + res.stderr).lower()

def test_self_link_rejected():
    res = run("python -m src.gdes link fake-id fake-id")
    assert res.returncode != 0 or "self" in (res.stdout + res.stderr).lower()

def test_dangling_link_rejected():
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    
    # Try to link to non-existent ID
    res = run(f"python -m src.gdes link {fin} 00000000-0000-0000-0000-000000000000")
    assert res.returncode != 0 or "not found" in (res.stdout + res.stderr).lower()

def test_validate_links_passes_on_clean_graph():
    res = run("python -m src.gdes validate-links")
    assert res.returncode == 0
