from __future__ import annotations

from typing import Any, Dict, List, Optional

import yaml

from .core import Config
from .models import CanonicalArtifact, ValidationReport


_FORBIDDEN_WORDS = {"password", "secret", "apikey", "api_key", "token"}


class Validator:
    def __init__(self, config: Optional[Config] = None) -> None:
        self._config = config or Config()
        self._config.ensure_dirs()

    def _concept_path(self, concept_name: str):
        base = self._config.paths.concepts
        candidates = [base / f"{concept_name}.yaml", base / f"{concept_name}.yml"]
        for p in candidates:
            if p.exists() and p.is_file():
                return p
        return candidates[0]

    def validate(self, canonical: CanonicalArtifact) -> ValidationReport:
        violations: List[str] = []

        concept_file = self._concept_path(canonical.concept)
        if not concept_file.exists():
            violations.append(
                f"Concept YAML not found for '{canonical.concept}' in {self._config.paths.concepts}"
            )
            return ValidationReport(
                artifact_id=canonical.id,
                concept=canonical.concept,
                checks={},
                result="fail",
                violations=violations,
            )

        with concept_file.open("r", encoding="utf-8") as f:
            concept_data: Dict[str, Any] = yaml.safe_load(f) or {}

        checks: Dict[str, Any] = {
            "contract": concept_data.get("contract"),
            "responsibilities": concept_data.get("responsibilities"),
            "boundaries": concept_data.get("boundaries"),
        }

        required_fields = [
            "id",
            "source",
            "created_at",
            "content",
            "concept",
            "type",
            "metadata",
        ]
        for field in required_fields:
            if getattr(canonical, field, None) is None:
                violations.append(f"Missing field: {field}")

        responsibilities = concept_data.get("responsibilities")
        if isinstance(responsibilities, list):
            if len(responsibilities) > 3:
                violations.append("Too many responsibilities listed (max 3)")
        elif responsibilities is not None:
            violations.append("Concept responsibilities must be a list if provided")

        lowered = canonical.content.lower()
        forbidden_found = [w for w in _FORBIDDEN_WORDS if w in lowered]
        if forbidden_found:
            violations.append(f"Forbidden words found in content: {sorted(forbidden_found)}")

        result = "pass" if not violations else "fail"

        return ValidationReport(
            artifact_id=canonical.id,
            concept=canonical.concept,
            checks=checks,
            result=result,
            violations=violations,
        )
