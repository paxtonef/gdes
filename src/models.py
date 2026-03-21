from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field


ArtifactType = Literal["code", "markdown", "config", "chat_export", "snippet"]
ValidationResult = Literal["pass", "fail"]


class PartialArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="UUID string")
    source: str
    created_at: datetime = Field(..., description="ISO timestamp")
    content: str


class CanonicalArtifact(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(..., description="UUID string")
    source: str
    created_at: datetime = Field(..., description="ISO timestamp")
    content: str

    concept: str
    type: str  # Concept-driven
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: str
    concept: str
    checks: Dict[str, Any] = Field(
        default_factory=dict,
        description="dict with contract/responsibilities/boundaries",
    )
    result: ValidationResult
    violations: List[str] = Field(default_factory=list)
