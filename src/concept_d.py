from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import List, Optional

from .core import Config
from .artifact import CanonicalArtifact, ValidationReport


class Registry:
    def __init__(self, config: Optional[Config] = None) -> None:
        self._config = config or Config()
        self._config.ensure_dirs()
        self._db_path = self._config.paths.output / "registry.db"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    content TEXT NOT NULL,
                    concept TEXT NOT NULL,
                    type TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    artifact_id TEXT PRIMARY KEY,
                    concept TEXT NOT NULL,
                    checks_json TEXT NOT NULL,
                    result TEXT NOT NULL,
                    violations_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(artifact_id) REFERENCES artifacts(id)
                )
                """
            )
            conn.commit()

    def store(self, artifact: CanonicalArtifact, report: ValidationReport) -> None:
        if report.result != "pass":
            raise ValueError("Registry only accepts artifacts that passed validation")

        if report.artifact_id != artifact.id:
            raise ValueError("Report artifact_id does not match artifact id")

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO artifacts(
                    id, source, created_at, content, concept, type, metadata_json
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.id,
                    artifact.source,
                    artifact.created_at.isoformat()
                    if isinstance(artifact.created_at, datetime)
                    else str(artifact.created_at),
                    artifact.content,
                    artifact.concept,
                    artifact.artifact_type,
                    json.dumps(artifact.metadata, ensure_ascii=False),
                ),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO reports(
                    artifact_id, concept, checks_json, result, violations_json, created_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    report.artifact_id,
                    report.concept,
                    json.dumps(report.checks, ensure_ascii=False),
                    report.result,
                    json.dumps(report.violations, ensure_ascii=False),
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()

    def search(self, concept: str) -> List[CanonicalArtifact]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE concept = ? ORDER BY created_at DESC",
                (concept,),
            ).fetchall()

        artifacts: List[CanonicalArtifact] = []
        for r in rows:
            artifacts.append(
                CanonicalArtifact(
                    id=r["id"],
                    source=r["source"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    content=r["content"],
                    concept=r["concept"],
                    artifact_type=r["type"],
                    metadata=json.loads(r["metadata_json"]),
                )
            )
        return artifacts

    def total_count(self) -> int:
        with self._connect() as conn:
            (n,) = conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()
        return int(n)

    def orphan_count(self) -> int:
        with self._connect() as conn:
            (n,) = conn.execute(
                """
                SELECT COUNT(*)
                FROM artifacts a
                LEFT JOIN reports r ON r.artifact_id = a.id
                WHERE r.artifact_id IS NULL
                """
            ).fetchone()
        return int(n)

    def search_all(self) -> List[CanonicalArtifact]:
        """Retrieve all artifacts across all concepts"""
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM artifacts ORDER BY created_at DESC"
            )
            rows = cursor.fetchall()
        
        return [
            CanonicalArtifact(
                id=r["id"],
                source=r["source"],
                created_at=datetime.fromisoformat(r["created_at"]),
                content=r["content"],
                concept=r["concept"],
                artifact_type=r["type"],
                metadata=json.loads(r["metadata_json"])
            )
            for r in rows
        ]
