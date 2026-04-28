"""Operational health checks"""
import sqlite3
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict

@dataclass
class HealthReport:
    total_nodes: int
    orphaned_nodes: int
    orphaned_percentage: float
    broken_refs: List[Dict]
    cycles_detected: List[List[str]]
    concept_distribution: Dict[str, int]
    integrity_score: float
    status: str

class IntegrityChecker:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        
    def check(self):
        if not self.db_path.exists() or self.db_path.stat().st_size == 0:
            return HealthReport(
                total_nodes=0, orphaned_nodes=0, orphaned_percentage=0.0,
                broken_refs=[], cycles_detected=[], concept_distribution={},
                integrity_score=1.0, status="DATABASE_EMPTY"
            )
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, concept, type, metadata_json FROM artifacts")
            rows = cursor.fetchall()
        except sqlite3.OperationalError as e:
            return HealthReport(
                total_nodes=0, orphaned_nodes=0, orphaned_percentage=0.0,
                broken_refs=[], cycles_detected=[], concept_distribution={},
                integrity_score=0.0, status=f"DB_ERROR: {e}"
            )
        
        nodes = {}
        edges = []
        
        for r in rows:
            node_id = r["id"]
            nodes[node_id] = {
                "concept": r["concept"],
                "type": r["type"]
            }
            # Extract relationships from metadata_json
            try:
                meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
                related = meta.get("related_to", [])
                for target in related:
                    edges.append({"source": node_id, "target": target, "relation": "related_to"})
            except json.JSONDecodeError:
                pass
        
        total = len(nodes)
        node_ids = set(nodes.keys())
        connected = set()
        broken = []
        
        for e in edges:
            connected.add(e["source"])
            connected.add(e["target"])
            if e["target"] not in node_ids:
                broken.append({"source": e["source"], "missing_target": e["target"]})
        
        orphaned = [n for n in nodes if n not in connected]
        orphan_pct = (len(orphaned)/total*100) if total else 0
        
        distribution = {}
        for n, data in nodes.items():
            c = data.get("concept", "unknown")
            distribution[c] = distribution.get(c, 0) + 1
        
        score = 1.0
        if orphan_pct > 5: score -= 0.3
        if broken: score -= 0.4
        
        return HealthReport(
            total_nodes=total,
            orphaned_nodes=len(orphaned),
            orphaned_percentage=orphan_pct,
            broken_refs=broken,
            cycles_detected=[],
            concept_distribution=distribution,
            integrity_score=max(0.0, score),
            status="OK"
        )
    
    def format_report(self, r):
        lines = [
            "=== GDES Health Report ===",
            f"Status: {r.status}",
            f"Total Nodes: {r.total_nodes}",
            f"Orphaned: {r.orphaned_nodes} ({r.orphaned_percentage:.1f}%)",
            f"Integrity Score: {r.integrity_score:.2f}",
            "", "Concept Distribution:"
        ]
        for c, n in sorted(r.concept_distribution.items()):
            lines.append(f"  {c}: {n}")
        if r.status == "DATABASE_EMPTY":
            lines.append("\nℹ️  Database is empty. Run 'gdes pipeline' to populate.")
        elif r.orphaned_percentage > 5:
            lines.append("\n⚠️  Orphaned nodes > 5%")
        if r.broken_refs:
            lines.append(f"\n❌ {len(r.broken_refs)} broken refs")
        return "\n".join(lines)
