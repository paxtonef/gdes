import json
import subprocess

def run(cmd: str):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def test_show_links_returns_expected_shape():
    # Setup
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/linking/security_alert.txt --concept security --type incident_report")
    
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    sec = json.loads(run("python -m src.gdes search --concept security --json").stdout)[0]["id"]
    run(f"python -m src.gdes link {fin} {sec}")
    
    res = run(f"python -m src.gdes show-links {fin}")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert "artifact_id" in data
    assert "related_to" in data
    assert isinstance(data["related_to"], list)

def test_search_related_to_filters_results():
    # Setup
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/linking/security_alert.txt --concept security --type incident_report")
    
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    sec = json.loads(run("python -m src.gdes search --concept security --json").stdout)[0]["id"]
    run(f"python -m src.gdes link {fin} {sec}")
    
    # Find who references sec
    res = run(f"python -m src.gdes search --related-to {sec} --json")
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert isinstance(data, list)
    assert len(data) >= 1
