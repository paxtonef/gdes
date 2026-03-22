import subprocess
import json
import pytest
from pathlib import Path

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def get_latest_partial_id():
    """Get the most recent partial artifact ID from staging"""
    partials_dir = Path.home() / ".gdes" / "inbox" / "partials"
    files = sorted(partials_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if files:
        return files[0].stem  # filename without extension
    return None

@pytest.fixture(autouse=True)
def clean_staging():
    import shutil
    from pathlib import Path
    for d in ["partials", "canonical", "reports"]:
        p = Path.home() / ".gdes" / "inbox" / d
        if p.exists():
            for f in p.glob("*.json"):
                f.unlink()

def test_finance_accepts_invoice():
    file = "tests/fixtures/finance/valid_invoice.txt"
    
    # Run pipeline instead of step-by-step (more reliable)
    res = run(f"python -m src.gdes pipeline --file {file} --concept finance --type invoice")
    assert res.returncode == 0, f"Pipeline failed: {res.stdout}{res.stderr}"
    
    # Verify it was stored
    search = run("python -m src.gdes search --concept finance --json")
    artifacts = json.loads(search.stdout)
    assert len(artifacts) >= 1, "Finance artifact not found"

def test_finance_rejects_security_type():
    file = "tests/fixtures/finance/valid_invoice.txt"
    
    # Try to use wrong type for finance concept
    res = run(f"python -m src.gdes pipeline --file {file} --concept finance --type incident_report")
    assert res.returncode != 0, "Should reject wrong type for concept"
    assert "failed" in res.stdout.lower() or "error" in res.stderr.lower() or "rollback" in res.stdout.lower()

def test_security_rejects_finance_type():
    file = "tests/fixtures/security/valid_incident.txt"
    
    # Try to use wrong type for security concept
    res = run(f"python -m src.gdes pipeline --file {file} --concept security --type invoice")
    assert res.returncode != 0, "Should reject wrong type for concept"
