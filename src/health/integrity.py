from __future__ import annotations
import sqlite3
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

@dataclass
class HealthReport:
    total_nodes: int = 0
    total_edges: int = 0
    orphan_nodes: List[str] = field(default_factory=list)
    dangling_refs: List[str] = field(default_factory=list)
    integrity_score: float = 1.0
    warnings: List[str] = field(default_factory=list)

class IntegrityChecker:
    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row

    def load_graph(self):
        import networkx as nx
        G = nx.Graph()
        cursor = self.conn.cursor()

        # Nodes from artifacts table
        cursor.execute("SELECT id, concept, type FROM artifacts")
        for row in cursor.fetchall():
            G.add_node(row["id"], concept=row["concept"], type=row["type"])

        # Edges from metadata_json related_to
        cursor.execute("SELECT id, metadata_json FROM artifacts")
        for row in cursor.fetchall():
            meta = json.loads(row["metadata_json"] or "{}")
            for target_id in meta.get("related_to", []):
                if G.has_node(row["id"]) and G.has_node(target_id):
                    G.add_edge(row["id"], target_id, relation="related_to")

        return G

    def check(self) -> HealthReport:
        G = self.load_graph()
        nodes = list(G.nodes())
        total = len(nodes)

        orphans = [n for n in nodes if G.degree(n) == 0]

        dangling = []
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM artifacts")
        all_ids = {row["id"] for row in cursor.fetchall()}
        cursor.execute("SELECT id, metadata_json FROM artifacts")
        for row in cursor.fetchall():
            meta = json.loads(row["metadata_json"] or "{}")
            for target_id in meta.get("related_to", []):
                if target_id not in all_ids:
                    dangling.append(f"{row['id']} -> {target_id}")

        score = 1.0
        if total > 0:
            score -= len(dangling) * 0.2
            score -= len(orphans) / total * 0.1
        score = max(0.0, round(score, 3))

        return HealthReport(
            total_nodes=total,
            total_edges=G.number_of_edges(),
            orphan_nodes=orphans,
            dangling_refs=dangling,
            integrity_score=score,
            warnings=[f"Dangling ref: {d}" for d in dangling],
        )

    def format_report(self, report: HealthReport) -> str:
        lines = [
            "GDES Health Report",
            "──────────────────",
            f"Nodes:           {report.total_nodes}",
            f"Edges:           {report.total_edges}",
            f"Orphans:         {len(report.orphan_nodes)}",
            f"Dangling refs:   {len(report.dangling_refs)}",
            f"Integrity score: {report.integrity_score:.3f}",
        ]
        if report.warnings:
            lines.append("\nWarnings:")
            for w in report.warnings:
                lines.append(f"  ⚠ {w}")
        else:
            lines.append("\n✅ No integrity issues found.")
        return "\n".join(lines)
