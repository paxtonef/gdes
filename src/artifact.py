"""Artifact data models"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

class PartialArtifact(BaseModel):
    id: str
    source: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def save(self, path):
        with open(path, 'w') as f:
            f.write(self.model_dump_json())

class CanonicalArtifact(BaseModel):
    id: str
    source: str
    content: str
    concept: str
    artifact_type: str
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def save(self, path):
        with open(path, 'w') as f:
            f.write(self.model_dump_json())

class ValidationReport(BaseModel):
    id: str
    result: str
    checks: List[str]
    duration_ms: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    def save(self, path):
        with open(path, 'w') as f:
            f.write(self.model_dump_json())
