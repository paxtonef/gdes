import subprocess
import json
from pathlib import Path

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def test_backup_restore_multi_concept():
    # Clean start
    run("rm -rf backups/*")
    
    # Create artifacts across multiple concepts
    run("python -m src.gdes pipeline --file tests/fixtures/finance/valid_invoice.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/security/valid_incident.txt --concept security --type incident_report")
    
    # Count before backup
    before = run("python -m src.gdes search --all --json")
    before_count = len(json.loads(before.stdout))
    assert before_count >= 2, f"Expected at least 2 artifacts, got {before_count}"
    
    # Backup
    run("python -m src.gdes backup")
    
    # Get latest backup
    import glob
    backups = sorted(glob.glob("backups/*.tar.gz"))
    assert len(backups) > 0
    latest = backups[-1]
    
    # Clear registry (destructive)
    db = Path.home() / ".gdes" / "registry.db"
    if db.exists():
        db.unlink()
    
    # Restore
    res = run(f"python -m src.gdes restore {latest} --force")
    assert res.returncode == 0, f"Restore failed: {res.stderr}"
    
    # Verify counts match
    after = run("python -m src.gdes search --all --json")
    after_count = len(json.loads(after.stdout))
    
    assert after_count == before_count, f"Count mismatch: {before_count} vs {after_count}"
    
    # Verify specific concepts exist
    finance = run("python -m src.gdes search --concept finance --json")
    security = run("python -m src.gdes search --concept security --json")
    
    assert len(json.loads(finance.stdout)) >= 1
    assert len(json.loads(security.stdout)) >= 1
