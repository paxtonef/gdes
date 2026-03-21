"""Concept C: Validator - Multi-concept validation with graceful path resolution"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

import yaml

from .core import Config
from .models import CanonicalArtifact, ValidationReport


_FORBIDDEN_WORDS = {"password", "secret", "apikey", "api_key", "token"}


class Validator:
    def __init__(self, config: Optional[Config] = None) -> None:
        self._config = config or Config()
        self._config.ensure_dirs()

    def _resolve_concept_paths(self) -> List[Path]:
        """PRIORITY 3: Same path resolution as Librarian"""
        paths = []
        seen = set()
        
        # 1. Project-local ./concepts/
        local_concepts = Path("./concepts").resolve()
        if local_concepts.exists():
            paths.append(local_concepts)
            seen.add(local_concepts)
        
        # 2. Configured path
        if hasattr(self._config, 'paths') and hasattr(self._config.paths, 'concepts'):
            cfg_path = Path(self._config.paths.concepts).resolve()
            if cfg_path not in seen:
                paths.append(cfg_path)
                seen.add(cfg_path)
        
        # 3. Fallback ~/.gdes/concepts/
        home_concepts = (Path.home() / ".gdes" / "concepts").resolve()
        if home_concepts not in seen:
            paths.append(home_concepts)
        
        return paths

    def _find_concept_file(self, concept_name: str) -> Optional[Path]:
        """Find concept YAML using multi-path resolution"""
        for base in self._resolve_concept_paths():
            candidate = base / f"{concept_name}.yaml"
            if candidate.exists():
                return candidate
        return None

    def validate(self, canonical: CanonicalArtifact) -> ValidationReport:
        violations: List[str] = []
        start_time = datetime.utcnow()

        # Find concept using multi-path resolution
        concept_file = self._find_concept_file(canonical.concept)
        
        if not concept_file:
            # PRIORITY 1: Controlled failure, not crash
            paths_checked = [str(b / f"{canonical.concept}.yaml") for b in self._resolve_concept_paths()]
            violations.append(
                f"Concept '{canonical.concept}' not found for validation. "
                f"Checked: {', '.join(paths_checked)}"
            )
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return ValidationReport(
                artifact_id=canonical.id,
                concept=canonical.concept,
                checks={},
                result="fail",
                violations=violations,
                duration_ms=duration_ms,
            )

        with concept_file.open("r", encoding="utf-8") as f:
            concept_data: Dict[str, Any] = yaml.safe_load(f) or {}

        # Run validation checks
        checks: Dict[str, Any] = {}
        
        # Contract check
        contract = concept_data.get("contract", {})
        checks["contract"] = bool(contract.get("input") and contract.get("output"))
        
        # Responsibilities check
        responsibilities = concept_data.get("responsibilities", [])
        checks["responsibilities"] = len(responsibilities) > 0
        
        # Boundaries check
        boundaries = concept_data.get("boundaries", {})
        forbidden = boundaries.get("explicitly_forbidden", [])
        
        # Content scan for forbidden patterns
        content_lower = canonical.content.lower()
        found_forbidden = [w for w in _FORBIDDEN_WORDS if w in content_lower]
        if found_forbidden:
            violations.append(f"Content contains forbidden terms: {found_forbidden}")
            checks["boundaries"] = False
        else:
            checks["boundaries"] = True
        
        result = "pass" if not violations and all(checks.values()) else "fail"
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return ValidationReport(
            artifact_id=canonical.id,
            concept=canonical.concept,
            checks=checks,
            result=result,
            violations=violations,
            duration_ms=duration_ms,
        )
