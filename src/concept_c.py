"""Concept C: Validator - Multi-concept validation with graceful path resolution"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

import yaml

from .core import Config
from .artifact import CanonicalArtifact, ValidationReport


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

    def _load_concept_with_inheritance(self, concept_name: str, visited: set = None) -> Dict[str, Any]:
        """Load concept with inheritance (copied from Librarian)"""
        if visited is None:
            visited = set()
        
        if concept_name in visited:
            raise ValueError(f"Circular inheritance: {concept_name}")
        visited.add(concept_name)
        
        concept_file = self._find_concept_file(concept_name)
        if not concept_file:
            raise ValueError(f"Concept {concept_name} not found")
        
        with open(concept_file) as f:
            concept = yaml.safe_load(f)
        
        # Handle inheritance like Librarian does
        if 'extends' in concept:
            base_name = concept['extends']
            base_concept = self._load_concept_with_inheritance(base_name, visited)
            
            merged = {}
            merged['concept_id'] = concept['concept_id']
            merged['identity'] = concept.get('identity', base_concept.get('identity', {}))
            merged['purpose'] = concept.get('purpose', base_concept.get('purpose', {}))
            
            merged['contract'] = base_concept.get('contract', {}).copy()
            if 'contract' in concept:
                if 'allowed_types' in concept['contract']:
                    merged['contract']['allowed_types'] = concept['contract']['allowed_types']
            
            merged['responsibilities'] = concept.get('responsibilities', [])
            
            merged['boundaries'] = base_concept.get('boundaries', {}).copy()
            if 'boundaries' in concept:
                base_forbidden = merged['boundaries'].get('system_wide_forbidden', [])
                child_forbidden = concept['boundaries'].get('own_forbidden', [])
                merged['boundaries']['system_wide_forbidden'] = list(set(base_forbidden + child_forbidden))
            
            return merged
        
        return concept


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
        # Load concept with inheritance resolution
        try:
            concept_data = self._load_concept_with_inheritance(canonical.concept)
        except ValueError as e:
            violations.append(f"Cannot load concept: {e}")
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            return ValidationReport(
                artifact_id=canonical.id,
                concept=canonical.concept,
                checks={},
                result="fail",
                violations=violations,
                duration_ms=duration_ms,
            )
        
        # concept_data already loaded with inheritance above

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
