"""GDES V1.16 -- Graph Export Engine

Export artifact graph to Mermaid or DOT format.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from pathlib import Path

from ..core import Config
from ..concept_d import Registry
from ..artifact import CanonicalArtifact


class GraphExporter:
    """Export artifact relations as Mermaid or DOT graph."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.registry = Registry(self.config)

    def build_edges(self) -> List[Tuple[str, str, Optional[str]]]:
        """Return [(source_id, target_id, relation_type)] for all typed relations."""
        edges: List[Tuple[str, str, Optional[str]]] = []
        artifacts = self.registry.search_all()
        for a in artifacts:
            rels = a.metadata.get('relation_types', {})
            for target_id, rel_type in rels.items():
                edges.append((a.id, target_id, rel_type))
        return edges

    def to_mermaid(self, edges: Optional[List[Tuple[str, str, Optional[str]]]] = None) -> str:
        """Generate Mermaid flowchart from edges."""
        if edges is None:
            edges = self.build_edges()
        lines = ['flowchart TD']
        seen_nodes: set = set()
        for src, tgt, rel in edges:
            src_short = src[:8]
            tgt_short = tgt[:8]
            seen_nodes.add(src_short)
            seen_nodes.add(tgt_short)
            if rel:
                lines.append(f'    {src_short} -->|{rel}| {tgt_short}')
            else:
                lines.append(f'    {src_short} --> {tgt_short}')
        return '\n'.join(lines)

    def to_dot(self, edges: Optional[List[Tuple[str, str, Optional[str]]]] = None) -> str:
        """Generate Graphviz DOT from edges."""
        if edges is None:
            edges = self.build_edges()
        lines = ['digraph G {', '    rankdir=LR;']
        seen_nodes: set = set()
        for src, tgt, rel in edges:
            src_short = src[:8]
            tgt_short = tgt[:8]
            seen_nodes.add(src_short)
            seen_nodes.add(tgt_short)
            label = f' [label="{rel}"]' if rel else ''
            lines.append(f'    "{src_short}" -> "{tgt_short}"{label};')
        lines.append('}')
        return '\n'.join(lines)

    def export(self, format: str = 'mermaid', output: Optional[Path] = None) -> str:
        """Export graph to string or file."""
        edges = self.build_edges()
        if format == 'mermaid':
            content = self.to_mermaid(edges)
        elif format == 'dot':
            content = self.to_dot(edges)
        else:
            raise ValueError(f'Unknown format: {format}. Use mermaid or dot.')

        if output:
            output.write_text(content, encoding='utf-8')
        return content
