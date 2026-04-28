"""GDES V1.17 — Artifact Diff Engine

Compare two artifacts by content, metadata, and relations.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .core import Config
from .concept_d import Registry
from .artifact import CanonicalArtifact


@dataclass
class DiffResult:
    identical: bool = True
    content_diff: List[str] = field(default_factory=list)
    metadata_added: Dict = field(default_factory=dict)
    metadata_removed: Dict = field(default_factory=dict)
    metadata_changed: Dict = field(default_factory=dict)
    relations_added: Dict = field(default_factory=dict)
    relations_removed: Dict = field(default_factory=dict)
    relations_changed: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "identical": self.identical,
            "content_changed": bool(self.content_diff),
            "metadata_added": self.metadata_added,
            "metadata_removed": self.metadata_removed,
            "metadata_changed": self.metadata_changed,
            "relations_added": self.relations_added,
            "relations_removed": self.relations_removed,
            "relations_changed": self.relations_changed,
        }


class ArtifactDiff:
    """Compare two artifacts."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.registry = Registry(self.config)

    def diff(self, id_a: str, id_b: str) -> DiffResult:
        all_artifacts = self.registry.search_all()
        a = next((x for x in all_artifacts if x.id == id_a), None)
        b = next((x for x in all_artifacts if x.id == id_b), None)

        if not a:
            raise ValueError(f"Artifact {id_a!r} not found")
        if not b:
            raise ValueError(f"Artifact {id_b!r} not found")

        result = DiffResult()

        # Content diff
        if a.content != b.content:
            result.identical = False
            result.content_diff = list(
                difflib.unified_diff(
                    a.content.splitlines(keepends=True),
                    b.content.splitlines(keepends=True),
                    fromfile=f"a ({id_a[:8]})",
                    tofile=f"b ({id_b[:8]})",
                    lineterm="",
                )
            )

        # Metadata diff
        meta_a = dict(a.metadata)
        meta_b = dict(b.metadata)
        keys_a = set(meta_a.keys())
        keys_b = set(meta_b.keys())

        for key in keys_a - keys_b:
            result.identical = False
            result.metadata_removed[key] = meta_a[key]

        for key in keys_b - keys_a:
            result.identical = False
            result.metadata_added[key] = meta_b[key]

        for key in keys_a & keys_b:
            if meta_a[key] != meta_b[key]:
                result.identical = False
                result.metadata_changed[key] = {"from": meta_a[key], "to": meta_b[key]}

        # Relation diff (typed relations)
        rel_a = meta_a.get("relation_types", {})
        rel_b = meta_b.get("relation_types", {})
        keys_ra = set(rel_a.keys())
        keys_rb = set(rel_b.keys())

        for key in keys_ra - keys_rb:
            result.identical = False
            result.relations_removed[key] = rel_a[key]

        for key in keys_rb - keys_ra:
            result.identical = False
            result.relations_added[key] = rel_b[key]

        for key in keys_ra & keys_rb:
            if rel_a[key] != rel_b[key]:
                result.identical = False
                result.relations_changed[key] = {"from": rel_a[key], "to": rel_b[key]}

        return result
