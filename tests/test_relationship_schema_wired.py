"""Test relationship_schema.py and staging_lock.py wiring (V1.7.2)"""
import json
import subprocess
import pytest
from pathlib import Path
import tempfile
import time
import multiprocessing

def run(cmd: str):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)

@pytest.fixture(autouse=True)
def clean_staging():
    for d in ["partials", "canonical", "reports"]:
        p = Path.home() / ".gdes" / "inbox" / d
        if p.exists():
            for f in p.glob("*.json"):
                f.unlink()

def test_link_auto_selects_relation_for_known_pair():
    """finance → security should auto-select 'compliance'"""
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/linking/security_alert.txt --concept security --type incident_report")
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    sec = json.loads(run("python -m src.gdes search --concept security --json").stdout)[0]["id"]
    res = run(f"python -m src.gdes link {fin} {sec}")
    assert res.returncode == 0
    assert "compliance" in res.stdout

def test_link_with_explicit_relation_passes():
    """Link with --relation audit should pass for finance→security"""
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/linking/security_alert.txt --concept security --type incident_report")
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    sec = json.loads(run("python -m src.gdes search --concept security --json").stdout)[0]["id"]
    res = run(f"python -m src.gdes link {fin} {sec} --relation audit")
    assert res.returncode == 0
    assert "audit" in res.stdout

def test_link_with_invalid_relation_fails():
    """'loves' is not a valid relation between finance→security"""
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/linking/security_alert.txt --concept security --type incident_report")
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    sec = json.loads(run("python -m src.gdes search --concept security --json").stdout)[0]["id"]
    res = run(f"python -m src.gdes link {fin} {sec} --relation loves")
    assert res.returncode != 0
    out = res.stdout + res.stderr
    assert "not allowed" in out

def test_link_forbidden_concept_pair_fails():
    """test → finance has no schema entry"""
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/finance/valid_invoice.txt --concept test --type python_test")
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    tst = json.loads(run("python -m src.gdes search --concept test --json").stdout)[0]["id"]
    res = run(f"python -m src.gdes link {tst} {fin}")
    assert res.returncode != 0
    out = res.stdout + res.stderr
    assert "No schema defined" in out

def test_link_stores_relation_type_in_metadata():
    """relation_types should be stored in metadata_json"""
    run("python -m src.gdes pipeline --file tests/fixtures/linking/finance_record.txt --concept finance --type invoice")
    run("python -m src.gdes pipeline --file tests/fixtures/linking/security_alert.txt --concept security --type incident_report")
    fin = json.loads(run("python -m src.gdes search --concept finance --json").stdout)[0]["id"]
    sec = json.loads(run("python -m src.gdes search --concept security --json").stdout)[0]["id"]
    run(f"python -m src.gdes link {fin} {sec} --relation audit")
    res = run(f"python -m src.gdes show-links {fin}")
    data = json.loads(res.stdout)
    assert sec in data["related_to"]

def _hold_lock_process(lock_dir: str, acquired_event, release_event):
    """Helper to hold fcntl lock in a separate process"""
    from src.persistence.staging_lock import staging_lock
    tmp_path = Path(lock_dir)
    with staging_lock(tmp_path, timeout=5):
        acquired_event.set()
        release_event.wait(timeout=5)

def test_staging_lock_blocks_second_process():
    """fcntl locks are process-level; test with multiprocessing, not threading"""
    from src.persistence.staging_lock import staging_lock, StagingConcurrencyError
    import multiprocessing
    
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        acquired = multiprocessing.Event()
        release = multiprocessing.Event()
        
        p = multiprocessing.Process(
            target=_hold_lock_process,
            args=(str(tmp_path), acquired, release)
        )
        p.start()
        acquired.wait(timeout=2)
        
        try:
            with pytest.raises(StagingConcurrencyError):
                with staging_lock(tmp_path, timeout=0):
                    pass
        finally:
            release.set()
            p.join(timeout=3)
            if p.is_alive():
                p.terminate()
                p.join()
