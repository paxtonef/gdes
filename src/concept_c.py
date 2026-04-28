"""Concept C: Validator — Multi-concept validation with unified inheritance resolver"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from .core import Config
from .artifact import CanonicalArtifact, ValidationReport
from .resolvers.concept_inheritance import (
    ConceptResolver,
    resolve_concept_paths,
    InheritanceError,
)

_FORBIDDEN_WORDS = {"password", "secret", "apikey", "api_key", "token"}


class Validator:
    def __init__(self, config: Optional[Config] = None) -> None:
        self._config = config or Config()
        self._config.ensure_dirs()
        self._resolver = ConceptResolver(resolve_concept_paths(self._config), strict=True)

    def validate(self, canonical: CanonicalArtifact) -> ValidationReport:
        violations: List[str] = []
        start_time = datetime.now(timezone.utc)

        try:
            concept_data = self._resolver.get_schema(canonical.concept)
        except InheritanceError as e:
            violations.append(f"Cannot load concept: {e}")
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return ValidationReport(
                artifact_id=canonical.id,
                concept=canonical.concept,
                checks={},
                result="fail",
                violations=violations,
                duration_ms=duration_ms,
            )

        checks: Dict[str, Any] = {}

        contract = concept_data.get("contract", {})
        checks["contract"] = bool(contract.get("input") and contract.get("output"))

        responsibilities = concept_data.get("responsibilities", [])
        checks["responsibilities"] = len(responsibilities) > 0

        content_lower = canonical.content.lower()
        found_forbidden = [w for w in _FORBIDDEN_WORDS if w in content_lower]
        if found_forbidden:
            violations.append(f"Content contains forbidden terms: {found_forbidden}")
            checks["boundaries"] = False
        else:
            checks["boundaries"] = True

        result = "pass" if not violations and all(checks.values()) else "fail"
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

        return ValidationReport(
            artifact_id=canonical.id,
            concept=canonical.concept,
            checks=checks,
            result=result,
            violations=violations,
            duration_ms=duration_ms,
        )
