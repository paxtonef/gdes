from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .core import Config
from .models import ArtifactType, CanonicalArtifact, PartialArtifact


_ALLOWED_TYPES = {"code", "markdown", "config", "chat_export", "snippet"}


class Librarian:
    def __init__(self, config: Optional[Config] = None) -> None:
        self._config = config or Config()
        self._config.ensure_dirs()

    def _concept_path(self, concept_name: str) -> Path:
        base = self._config.paths.concepts
        candidates = [
            base / f"{concept_name}.yaml",
            base / f"{concept_name}.yml",
        ]
        for p in candidates:
            if p.exists() and p.is_file():
                return p
        return candidates[0]

    def load_concepts(self) -> Dict[str, Dict[str, Any]]:
        concepts: Dict[str, Dict[str, Any]] = {}
        for p in sorted(self._config.paths.concepts.glob("*.y*ml")):
            if not p.is_file():
                continue
            with p.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            concepts[p.stem] = data
        return concepts

    def tag(
        self,
        partial: PartialArtifact,
        concept_name: str,
        type: ArtifactType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CanonicalArtifact:
        if str(type) not in _ALLOWED_TYPES:
            raise ValueError(f"Invalid type: {type}. Allowed: {sorted(_ALLOWED_TYPES)}")

        concept_file = self._concept_path(concept_name)
        if not concept_file.exists():
            raise FileNotFoundError(
                f"Concept YAML not found for '{concept_name}' in {self._config.paths.concepts}"
            )

        with concept_file.open("r", encoding="utf-8") as f:
            concept_data = yaml.safe_load(f) or {}

        if "boundaries" not in concept_data:
            raise ValueError(f"Concept '{concept_name}' missing required 'boundaries:' section")

        return CanonicalArtifact(
            id=partial.id,
            source=partial.source,
            created_at=partial.created_at,
            content=partial.content,
            concept=concept_name,
            type=type,
            metadata=metadata or {},
        )
