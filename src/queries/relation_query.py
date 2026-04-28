"""GDES V1.12 — Relation Query Engine

Query artifacts by typed relation stored in metadata.relation_types.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..core import Config
from ..artifact import CanonicalArtifact
from ..concept_d import Registry


class RelationQuery:
    """Query engine for typed artifact relations."""

    def __init__(self, config: Optional[Config] = None):
        self._config = config or Config()
        self._registry = Registry(self._config)

    def get_relations(self, artifact_id: str) -> Dict[str, str]:
        """Return {related_id: relation_type} for an artifact."""
        all_artifacts = self._registry.search_all()
        artifact = next((a for a in all_artifacts if a.id == artifact_id), None)
        if not artifact:
            return {}
        return dict(artifact.metadata.get("relation_types", {}))

    def get_incoming(self, artifact_id: str) -> List[Tuple[str, str]]:
        """Return [(source_id, relation_type)] pointing to artifact_id."""
        all_artifacts = self._registry.search_all()
        incoming: List[Tuple[str, str]] = []
        for a in all_artifacts:
            rels = a.metadata.get("relation_types", {})
            if artifact_id in rels:
                incoming.append((a.id, rels[artifact_id]))
        return incoming

    def search_by_relation(
        self,
        relation: Optional[str] = None,
        source_concept: Optional[str] = None,
        target_concept: Optional[str] = None,
    ) -> List[CanonicalArtifact]:
        """Search artifacts by relation type and optional concept filters."""
        all_artifacts = self._registry.search_all()
        results: List[CanonicalArtifact] = []

        for a in all_artifacts:
            rels = a.metadata.get("relation_types", {})
            if not rels:
                continue

            if source_concept and a.concept != source_concept:
                continue

            matched = False
            for related_id, rel_type in rels.items():
                if relation and rel_type != relation:
                    continue
                if target_concept:
                    target = next(
                        (t for t in all_artifacts if t.id == related_id), None
                    )
                    if not target or target.concept != target_concept:
                        continue
                matched = True
                break

            if matched:
                results.append(a)

        return results
