"""Concept B: Librarian - Multi-concept governance with graceful validation"""
import yaml
from pathlib import Path
from typing import List

from .artifact import CanonicalArtifact, PartialArtifact

class ConceptValidationError(Exception):
    """Controlled failure for concept validation - no traceback"""
    pass

class Librarian:
    def __init__(self, config):
        self._config = config

    def _resolve_concept_paths(self) -> List[Path]:
        """Deterministic path resolution"""
        paths = []

        # 1. project-local
        paths.append(Path.cwd() / "concepts")

        # 2. config (optional)
        if hasattr(self._config, "paths") and hasattr(self._config.paths, "concepts"):
            paths.append(Path(self._config.paths.concepts).expanduser())

        # 3. fallback
        paths.append(Path.home() / ".gdes" / "concepts")

        return paths

    def tag(self, partial, concept_name: str, artifact_type: str):
        """Tag partial artifact into canonical form"""
        concept_paths = self._resolve_concept_paths()
        concept_file = None
        checked_paths = []

        for path in concept_paths:
            candidate = path / f"{concept_name}.yaml"
            checked_paths.append(str(candidate))
            if candidate.exists():
                concept_file = candidate
                break

        if not concept_file:
            error_msg = f"Concept '{concept_name}' not found.\nPaths checked:\n"
            for p in checked_paths:
                error_msg += f"  - {p}\n"
            raise ConceptValidationError(error_msg)

        with open(concept_file, "r", encoding="utf-8") as f:
            concept = yaml.safe_load(f) or {}

        if "boundaries" not in concept:
            raise ConceptValidationError(
                f"Concept '{concept_name}' missing required 'boundaries:' section"
            )

        allowed_types = concept.get("allowed_types")
        contract = concept.get("contract") or {}
        if allowed_types is None and isinstance(contract, dict):
            allowed_types = contract.get("allowed_types")
        if isinstance(allowed_types, list) and allowed_types and artifact_type not in allowed_types:
            raise ConceptValidationError(
                f"Type '{artifact_type}' not allowed for concept '{concept_name}'. Allowed: {allowed_types}"
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
