from pathlib import Path
import yaml

def test_concepts_load():
    for f in Path("concepts").glob("*.yaml"):
        data = yaml.safe_load(open(f))
        assert "concept_id" in data
        assert "contract" in data
        assert "allowed_types" in data["contract"]
        assert isinstance(data["contract"]["allowed_types"], list)

def test_all_concepts_present():
    concepts = list(Path("concepts").glob("*.yaml"))
    ids = [yaml.safe_load(open(f))["concept_id"] for f in concepts]
    assert "config" in ids
    assert "test" in ids
    assert "finance" in ids
    assert "security" in ids
