import json
import subprocess
from pathlib import Path

def run(cmd: str):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

def latest_backup() -> str:
    backups = sorted(Path("backups").glob("*.tar.gz"))
    assert backups, "No backups found"
    return str(backups[-1])

def test_restore_preserves_links_and_validation_passes():
    # Baseline validation
    res_before = run("python -m src.gdes validate-links")
    assert res_before.returncode == 0

    # Backup current state
    backup_res = run("python -m src.gdes backup")
    assert backup_res.returncode == 0

    # Restore
    restore_res = run(f"python -m src.gdes restore {latest_backup()} --force")
    assert restore_res.returncode == 0

    # Validate links after restore
    res_after = run("python -m src.gdes validate-links")
    assert res_after.returncode == 0
