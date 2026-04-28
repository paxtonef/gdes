"""GDES V1.14 -- Concept Schema Migration"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .core import Config
from .concept_d import Registry
from .concept_c import Validator
from .resolvers.concept_inheritance import ConceptResolver, resolve_concept_paths, InheritanceError, AbstractConceptError
from .artifact import CanonicalArtifact


@dataclass
class MigrationReport:
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    drift: List[Dict] = field(default_factory=list)
    unchanged: int = 0

    def to_dict(self) -> Dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "unchanged": self.unchanged,
            "drift": self.drift,
        }


class SchemaMigration:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.registry = Registry(self.config)
        self.validator = Validator(self.config)
        self.resolver = ConceptResolver(resolve_concept_paths(self.config), strict=True)

    def run(self, apply: bool = False) -> MigrationReport:
        report = MigrationReport()
        all_artifacts = self.registry.search_all()

        for artifact in all_artifacts:
            report.total += 1
            try:
                self.resolver.get_schema(artifact.concept)
            except (InheritanceError, AbstractConceptError) as e:
                report.skipped += 1
                report.drift.append({"id": artifact.id, "concept": artifact.concept, "status": "skipped", "reason": str(e)})
                continue

            canonical = CanonicalArtifact(
                id=artifact.id, source=artifact.source, created_at=artifact.created_at,
                content=artifact.content, concept=artifact.concept,
                artifact_type=artifact.artifact_type, metadata=artifact.metadata,
            )
            new_report = self.validator.validate(canonical)

            if new_report.result == "pass":
                report.passed += 1
            else:
                report.failed += 1
                report.drift.append({"id": artifact.id, "concept": artifact.concept, "status": "failed", "violations": new_report.violations, "checks": new_report.checks})

            if apply:
                with self.registry._connect() as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO reports(artifact_id, concept, checks_json, result, violations_json, created_at) VALUES(?, ?, ?, ?, ?, ?)",
                        (new_report.artifact_id, new_report.concept, json.dumps(new_report.checks), new_report.result, json.dumps(new_report.violations), datetime.now(timezone.utc).isoformat()),
                    )
                    conn.commit()
        return report
