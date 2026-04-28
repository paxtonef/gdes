"""GDES V1.13 -- Batch Pipeline"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .core import Config
from .concept_a import Ingestor
from .concept_b import Librarian, ConceptValidationError
from .concept_c import Validator
from .concept_d import Registry
from .persistence.staging_lock import staging_lock, StagingConcurrencyError


class BatchResult:
    def __init__(self):
        self.success: List[Dict] = []
        self.failed: List[Dict] = []
        self.errors: List[Dict] = []

    @property
    def success_count(self) -> int:
        return len(self.success)

    @property
    def fail_count(self) -> int:
        return len(self.failed)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    def to_dict(self) -> Dict:
        return {
            "total": self.success_count + self.fail_count + self.error_count,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "error_count": self.error_count,
            "success": self.success,
            "failed": self.failed,
            "errors": self.errors,
        }


class BatchPipeline:
    def __init__(self, config: Config, concept_name: str, artifact_type: str, dry_run: bool = False):
        self.config = config
        self.concept_name = concept_name
        self.artifact_type = artifact_type
        self.dry_run = dry_run
        self.result = BatchResult()

    def run(self, files: List[Path]) -> BatchResult:
        with staging_lock(self.config.paths.inbox, timeout=5):
            for file_path in files:
                self._process_one(file_path)
        return self.result

    def _process_one(self, file_path: Path) -> None:
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            self.result.errors.append({"file": str(file_path), "stage": "read", "error": str(e)})
            return

        try:
            partial = Ingestor().ingest(content=content, source=str(file_path))
            canonical = Librarian(self.config).tag(partial=partial, concept_name=self.concept_name, artifact_type=self.artifact_type)
            report = Validator(self.config).validate(canonical)

            if report.result != "pass":
                self.result.failed.append({"file": str(file_path), "id": canonical.id, "stage": "C", "violations": report.violations})
                return

            if not self.dry_run:
                Registry(self.config).store(canonical, report)

            self.result.success.append({"file": str(file_path), "id": canonical.id, "dry_run": self.dry_run})

        except ConceptValidationError as e:
            self.result.failed.append({"file": str(file_path), "stage": "B", "error": str(e)})
        except StagingConcurrencyError as e:
            self.result.errors.append({"file": str(file_path), "stage": "lock", "error": str(e)})
        except Exception as e:
            self.result.errors.append({"file": str(file_path), "stage": "unknown", "error": str(e)})
