"""Concept B: Librarian - Multi-concept governance with graceful validation"""
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List

class ConceptValidationError(Exception):
    """Controlled failure for concept validation - no traceback"""
    pass

class Librarian:
    def __init__(self, config):
        self._config = config

    def tag(self, partial, concept_name: str, artifact_type: str):
        """PRIORITY 1: Graceful concept lookup with deterministic paths"""
        concept_paths = self._resolve_concept_paths()
        concept_file = None
        checked_paths = []
        
        for path in concept_paths:
            candidate = Path(path) / f"{concept_name}.yaml"
            checked_paths.append(str(candidate))
            if candidate.exists():
                concept_file = candidate
                break
        
        if not concept_file:
            # CONTROLLED FAILURE: No traceback, clear diagnostics
            error_msg = (
                f"Concept '{concept_name}' not found.\n"
                f"Search paths checked ({len(checked_paths)}):\n"
            )
            for p in checked_paths:
                error_msg += f"  - {p}\n"
            error_msg += (
                f"\nRecovery options:\n"
                f"  1. Create {checked_paths[0]}\n"
                f"  2. Verify concept_id in YAML matches '{concept_name}'\n"
                f"  3. Run from project root containing ./concepts/"
            )
            raise ConceptValidationError(error_msg)
        
        # Load and validate concept YAML
        try:
            with open(concept_file) as f:
                concept = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConceptValidationError(f"Invalid YAML in {concept_file}: {e}")
        
        # Validate concept_id matches filename
        if concept.get('concept_id') != concept_name:
            raise ConceptValidationError(
                f"Mismatch: filename '{concept_name}.yaml' vs concept_id '{concept.get('concept_id')}'"
            )
        
        # PRIORITY 4: Per-concept type validation
        allowed_types = concept.get('contract', {}).get('allowed_types', 
            ['code', 'markdown', 'config', 'chat_export', 'snippet', 'documentation'])
        
        if artifact_type not in allowed_types:
            raise ConceptValidationError(
                f"Type '{artifact_type}' not allowed for concept '{concept_name}'.\n"
                f"Allowed: {allowed_types}\n"
                f"Check concept YAML contract.allowed_types"
            )
        
        # Create canonical artifact
        return self._create_canonical(partial, concept, artifact_type)

    def _resolve_concept_paths(self) -> List[Path]:
        """PRIORITY 3: Deterministic path resolution - project-local first"""
        seen = set()
        paths = []
        
        # 1. Project-local ./concepts/ (if exists)
        local_concepts = Path("./concepts").resolve()
        if local_concepts.exists():
            paths.append(local_concepts)
            seen.add(local_concepts)
        
        # 2. Configured path (if set and different)
        if hasattr(self._config, 'paths') and hasattr(self._config.paths, 'concepts'):
            cfg_path = Path(self._config.paths.concepts).resolve()
            if cfg_path not in seen:
                paths.append(cfg_path)
                seen.add(cfg_path)
        
        # 3. Fallback ~/.gdes/concepts/ (if different)
        home_concepts = (Path.home() / ".gdes" / "concepts").resolve()
        if home_concepts not in seen:
            paths.append(home_concepts)
        
        return paths

    def _create_canonical(self, partial, concept: Dict[str, Any], artifact_type: str):
        from .artifact import CanonicalArtifact
        return CanonicalArtifact(
            id=partial.id,
            source=partial.source,
            content=partial.content,
            concept=concept['concept_id'],
            artifact_type=artifact_type,
            metadata={
                'concept_name': concept['identity']['name'],
                'concept_purpose': concept['purpose']['solves']
            }
        )
