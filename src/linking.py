from __future__ import annotations
from typing import Dict, List, Set


def normalize_refs(artifact: Dict) -> Dict:
    refs = artifact.get("related_to", [])
    if refs is None:
        refs = []
    seen = set()
    normalized = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            normalized.append(ref)
    artifact["related_to"] = normalized
    return artifact


def add_reference(artifact: Dict, target_id: str) -> Dict:
    artifact = normalize_refs(artifact)
    source_id = artifact.get("id")

    if source_id is not None and str(source_id) == str(target_id):
        raise ValueError("self-link is not allowed")

    if target_id in artifact["related_to"]:
        raise ValueError("duplicate link is not allowed")

    artifact["related_to"].append(target_id)
    return artifact


def remove_reference(artifact: Dict, target_id: str) -> Dict:
    artifact = normalize_refs(artifact)
    artifact["related_to"] = [ref for ref in artifact["related_to"] if ref != target_id]
    return artifact


def validate_references(artifact: Dict, existing_ids: Set[str]) -> List[str]:
    errors: List[str] = []
    source_id = str(artifact.get("id", ""))

    refs = artifact.get("related_to", []) or []
    seen = set()

    for ref in refs:
        ref_s = str(ref)

        if ref_s == source_id and source_id:
            errors.append("self-link is not allowed")
            continue

        if ref_s in seen:
            errors.append(f"duplicate reference: {ref_s}")
            continue
        seen.add(ref_s)

        if ref_s not in existing_ids:
            errors.append(f"dangling reference: {ref_s}")

    return errors


def get_links(artifact: Dict) -> List[str]:
    return list((artifact.get("related_to") or []))
