"""Concept B: Librarian — Multi-concept governance with unified inheritance resolver"""
from __future__ import annotations

from pathlib import Path
from typing import List

from .artifact import CanonicalArtifact, PartialArtifact
from .resolvers.concept_inheritance import (
    ConceptResolver,
    resolve_concept_paths,
    InheritanceError,
    AbstractConceptError,
)


class ConceptValidationError(Exception):
    """Controlled failure for concept validation - no traceback"""
    pass


class Librarian:
    def __init__(self, config):
        self._config = config
        self._resolver = ConceptResolver(resolve_concept_paths(config), strict=True)

    def tag(self, partial, concept_name: str, artifact_type: str):
        try:
            concept_data = self._resolver.get_schema(concept_name)
        except (InheritanceError, AbstractConceptError) as e:
            raise ConceptValidationError(str(e))

        if "boundaries" not in concept_data:
            raise ConceptValidationError(
                f"Concept '{concept_name}' missing required 'boundaries:' section"
            )

        allowed_types = concept_data.get("contract", {}).get("allowed_types", [])
        if isinstance(allowed_types, list) and allowed_types and artifact_type not in allowed_types:
            raise ConceptValidationError(
                f"Type '{artifact_type}' not allowed for concept '{concept_name}'. "
                f"Allowed: {allowed_types}"
            )

        if isinstance(partial, PartialArtifact):
            src = partial.source
            created_at = partial.created_at
        else:
            src = getattr(partial, "source", "unknown")
            created_at = getattr(partial, "created_at", None)

        return CanonicalArtifact(
            id=partial.id,
            source=src,
            created_at=created_at,
            content=partial.content,
            concept=concept_name,
            artifact_type=artifact_type,
            metadata=getattr(partial, "metadata", {}),
        )
