from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .models import PartialArtifact


class Ingestor:
    def ingest(self, content: str, source: str) -> PartialArtifact:
        return PartialArtifact(
            id=str(uuid4()),
            source=source,
            created_at=datetime.now(timezone.utc),
            content=content,
        )
