from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class Paths:
    base: Path
    concepts: Path
    output: Path
    inbox: Path
    logs: Path


class Config:
    _instance: Optional["Config"] = None
    _lock: Lock = Lock()

    def __new__(cls) -> "Config":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        home = Path(os.path.expanduser("~"))
        base = home / ".gdes"

        self.paths = Paths(
            base=base,
            concepts=base / "concepts",
            output=base / "output",
            inbox=base / "inbox",
            logs=base / "logs",
        )

        self._initialized = True

    def ensure_dirs(self) -> None:
        self.paths.base.mkdir(parents=True, exist_ok=True)
        self.paths.concepts.mkdir(parents=True, exist_ok=True)
        self.paths.output.mkdir(parents=True, exist_ok=True)
        self.paths.inbox.mkdir(parents=True, exist_ok=True)
        self.paths.logs.mkdir(parents=True, exist_ok=True)


class AuditLogger:
    def __init__(self, config: Optional[Config] = None) -> None:
        self._config = config or Config()
        self._config.ensure_dirs()
        self._log_path = self._config.paths.logs / "audit.log"
        self._write_lock = Lock()

    def log(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        payload: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "data": data or {},
        }

        line = json.dumps(payload, ensure_ascii=False)
        with self._write_lock:
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
