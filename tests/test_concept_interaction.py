import subprocess
import json
import pytest
from pathlib import Path

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

@pytest.fixture(autouse=True)
def clean_staging():
    import shutil
    from pathlib import Path
    for d in ["partials", "canonical", "reports"]:
        p = Path.home() / ".gdes" / "inbox" / d
        if p.exists():
            for f in p.glob("*.json"):
                f.unlink()

def test_finance_security_workflow():
    """Finance invoice triggers security review (cross-concept workflow)"""
    # Create finance artifact
    res = run("python -m src.gdes pipeline --file tests/fixtures/finance/valid_invoice.txt --concept finance --type invoice")
    assert res.returncode == 0, f"Finance pipeline failed: {res.stdout}"
    
    # Get finance artifact ID
    finance_search = run("python -m src.gdes search --concept finance --json")
    finance_artifacts = json.loads(finance_search.stdout)
    assert len(finance_artifacts) >= 1
    finance_id = finance_artifacts[0]["id"]
    
    # Create security review referencing finance
    res = run("python -m src.gdes pipeline --file tests/fixtures/security/valid_incident.txt --concept security --type incident_report")
    assert res.returncode == 0, f"Security pipeline failed: {res.stdout}"
    
    # Get security artifact ID
    sec_search = run("python -m src.gdes search --concept security --json")
    sec_artifacts = json.loads(sec_search.stdout)
    assert len(sec_artifacts) >= 1
    sec_id = sec_artifacts[0]["id"]
    
    # Link them: security references finance (security incident related to invoice)
    link_res = run(f"python -m src.gdes link {sec_id} {finance_id}")
    assert link_res.returncode == 0, f"Link failed: {link_res.stderr}"
    
    # Verify link exists
    refs_res = run(f"python -m src.gdes refs {sec_id}")
    assert finance_id in refs_res.stdout, f"Reference not found in output: {refs_res.stdout}"

def test_cross_concept_query():
    """Search across concepts works independently"""
    # Create artifacts in both concepts
    run("python -m src.gdes pipeline --file tests/fixtures/finance/valid_invoice.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/security/valid_incident.txt --concept security --type incident_report")
    
    # Query each concept separately
    finance = run("python -m src.gdes search --concept finance --json")
    security = run("python -m src.gdes search --concept security --json")
    
    finance_count = len(json.loads(finance.stdout))
    security_count = len(json.loads(security.stdout))
    
    assert finance_count >= 1, "Finance concept empty"
    assert security_count >= 1, "Security concept empty"

def test_invalid_reference_rejected():
    """Linking to non-existent artifact fails"""
    res = run("python -m src.gdes link fake-id-123 real-id-456")
    assert res.returncode != 0, "Should reject invalid artifact ID"

def test_persistence_keeps_references():
    """Backup/restore preserves cross-concept links"""
    import glob
    
    # Setup: finance + security + link
    run("python -m src.gdes pipeline --file tests/fixtures/finance/valid_invoice.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/security/valid_incident.txt --concept security --type incident_report")
    
    # Get IDs and link
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    sec = json.loads(run("python -m src.gdes search --concept security --json").stdout)[0]["id"]
    run(f"python -m src.gdes link {sec} {fin}")
    
    # Backup
    run("python -m src.gdes backup")
    latest = sorted(glob.glob("backups/*.tar.gz"))[-1]
    
    # Clear and restore
    db = Path.home() / ".gdes" / "registry.db"
    if db.exists():
        db.unlink()
    
    res = run(f"python -m src.gdes restore {latest} --force")
    assert res.returncode == 0, f"Restore failed: {res.stderr}"
    
    # Verify link intact
    refs = run(f"python -m src.gdes refs {sec}")
    assert fin in refs.stdout, f"Reference lost after restore"
