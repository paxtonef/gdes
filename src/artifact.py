"""Artifact data models"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ValidationResult = Literal["pass", "fail"]


class PartialArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content: str


class CanonicalArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source: str
    created_at: datetime
    content: str

    concept: str
    artifact_type: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: str
    concept: str
    checks: Dict[str, Any] = Field(default_factory=dict)
    result: ValidationResult
    violations: List[str] = Field(default_factory=list)
    duration_ms: Optional[int] = None
