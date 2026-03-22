import subprocess
import pytest

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

def test_pipeline_finance():
    res = run("python -m src.gdes pipeline --file tests/fixtures/finance/valid_invoice.txt --concept finance --type invoice")
    assert res.returncode == 0, f"Finance pipeline failed: {res.stdout}{res.stderr}"

def test_pipeline_security():
    res = run("python -m src.gdes pipeline --file tests/fixtures/security/valid_incident.txt --concept security --type incident_report")
    assert res.returncode == 0, f"Security pipeline failed: {res.stdout}{res.stderr}"

def test_pipeline_my_tool():
    # Use valid type for my_tool: code, snippet, or config (not python_test)
    res = run("python -m src.gdes pipeline --file tests/fixtures/finance/valid_invoice.txt --concept my_tool --type code")
    assert res.returncode == 0, f"My tool pipeline failed: {res.stdout}{res.stderr}"

def test_pipeline_test_concept():
    # test concept allows python_test
    res = run("python -m src.gdes pipeline --file tests/fixtures/finance/valid_invoice.txt --concept test --type python_test")
    assert res.returncode == 0, f"Test concept pipeline failed: {res.stdout}{res.stderr}"
