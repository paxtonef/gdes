"""
GDES V1.10 — Unified Concept Inheritance Resolver
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Dict, Any, List, Set, Optional
from collections import deque


class InheritanceError(Exception):
    pass


class CycleError(InheritanceError):
    pass


class MissingParentError(InheritanceError):
    pass


class AbstractConceptError(InheritanceError):
    pass


class ConceptResolver:
    def __init__(self, concept_paths: List[Path], strict: bool = True):
        self.concept_paths = [Path(p).expanduser().resolve() for p in concept_paths]
        self.strict = strict
        self._raw: Dict[str, Dict[str, Any]] = {}
        self._resolved: Dict[str, Dict[str, Any]] = {}
        self._load_all()
        self._resolve_all()

    def _find_concept_file(self, name: str) -> Optional[Path]:
        for base in self.concept_paths:
            candidate = base / f"{name}.yaml"
            if candidate.exists():
                return candidate
        return None

    def _load_all(self) -> None:
        seen: Set[Path] = set()
        for base in self.concept_paths:
            if not base.exists():
                continue
            for path in sorted(base.glob("*.yaml")):
                if path in seen:
                    continue
                seen.add(path)
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                cid = data.get("concept_id")
                if cid:
                    self._raw[cid] = data

    def _resolve_all(self) -> None:
        graph: Dict[str, List[str]] = {n: [] for n in self._raw}
        in_degree: Dict[str, int] = {n: 0 for n in self._raw}

        for name, data in self._raw.items():
            parent = self._get_extends(data)
            if parent:
                if parent not in self._raw:
                    raise MissingParentError(
                        f"Concept '{name}' extends unknown parent '{parent}'"
                    )
                graph[parent].append(name)
                in_degree[name] += 1

        queue = deque([n for n, d in in_degree.items() if d == 0])
        order: List[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for child in graph.get(node, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(order) != len(self._raw):
            remaining = [n for n, d in in_degree.items() if d > 0]
            raise CycleError(f"Circular inheritance detected among: {remaining}")

        for name in order:
            self._resolved[name] = self._resolve_one(name)

    def _get_extends(self, data: Dict[str, Any]) -> Optional[str]:
        extends = data.get("meta", {}).get("extends")
        if extends is None or extends == "null":
            extends = data.get("extends")
        if extends is None or extends == "null":
            return None
        return str(extends)

    def _resolve_one(self, name: str) -> Dict[str, Any]:
        raw = self._raw[name]
        parent_name = self._get_extends(raw)

        if parent_name:
            merged = self._smart_merge(
                self._deep_copy(self._resolved[parent_name]),
                self._deep_copy(raw),
            )
        else:
            merged = self._deep_copy(raw)

        meta = merged.setdefault("meta", {})
        meta.pop("extends", None)
        meta["resolved"] = True
        meta["resolved_version"] = "1.10.0"
        return merged

    def _deep_copy(self, obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._deep_copy(v) for v in obj]
        return obj

    _LIST_UNION_KEYS: Set[str] = {
        "responsibilities",
        "explicitly_forbidden",
        "drift_warnings",
    }

    def _smart_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key in set(base) | set(override):
            if key in override and key in base:
                b_val, o_val = base[key], override[key]
                if isinstance(b_val, dict) and isinstance(o_val, dict):
                    result[key] = self._smart_merge(b_val, o_val)
                elif isinstance(b_val, list) and isinstance(o_val, list):
                    if key in self._LIST_UNION_KEYS:
                        seen: Set[str] = set()
                        unioned: List[Any] = []
                        for item in b_val + o_val:
                            s = str(item)
                            if s not in seen:
                                seen.add(s)
                                unioned.append(item)
                        result[key] = unioned
                    else:
                        result[key] = o_val
                else:
                    result[key] = o_val
            elif key in override:
                result[key] = override[key]
            else:
                result[key] = base[key]
        return result

    def get_schema(self, concept: str) -> Dict[str, Any]:
        if concept not in self._resolved:
            raise InheritanceError(f"Unknown concept: {concept}")
        schema = self._resolved[concept]
        if self.strict and schema.get("meta", {}).get("abstract"):
            raise AbstractConceptError(f"Cannot instantiate abstract concept '{concept}'")
        return schema

    def list_concepts(self) -> List[str]:
        return sorted(self._resolved.keys())

    def get_lineage(self, concept: str) -> List[str]:
        if concept not in self._raw:
            raise InheritanceError(f"Unknown concept: {concept}")
        chain: List[str] = []
        current: str = concept
        visited: Set[str] = set()
        while current:
            if current in visited:
                raise CycleError(f"Cycle in lineage of '{concept}'")
            visited.add(current)
            chain.append(current)
            current = self._get_extends(self._raw[current]) or ""
        return list(reversed(chain))

    def is_abstract(self, concept: str) -> bool:
        if concept not in self._resolved:
            raise InheritanceError(f"Unknown concept: {concept}")
        return bool(self._resolved[concept].get("meta", {}).get("abstract"))


def resolve_concept_paths(config=None) -> List[Path]:
    paths: List[Path] = []
    seen: Set[Path] = set()
    local = Path("./concepts").resolve()
    if local.exists():
        paths.append(local)
        seen.add(local)
    if config is not None and hasattr(config, "paths") and hasattr(config.paths, "concepts"):
        cfg_path = Path(config.paths.concepts).resolve()
        if cfg_path not in seen:
            paths.append(cfg_path)
            seen.add(cfg_path)
    home_path = (Path.home() / ".gdes" / "concepts").resolve()
    if home_path not in seen:
        paths.append(home_path)
    return paths
