from collections import deque
from typing import Dict, List, Optional


def build_adjacency(artifacts):
    """
    artifacts: list of dicts with keys: id, related_to, concept, type
    returns:
        graph: dict {id: [neighbors]}
        meta:  dict {id: {"concept": ..., "type": ...}}
    """
    graph = {}
    meta = {}
    for a in artifacts:
        node = str(a["id"])
        refs = [str(r) for r in a.get("related_to", []) or []]
        graph[node] = refs
        meta[node] = {
            "concept": a.get("concept"),
            "type": a.get("type"),
        }
    return graph, meta


def _matches(meta, node_id, concept=None, type_=None):
    """Return True if node satisfies all supplied filters."""
    if node_id not in meta:
        return False
    m = meta[node_id]
    if concept is not None and m.get("concept") != concept:
        return False
    if type_ is not None and m.get("type") != type_:
        return False
    return True


def neighbors(graph, meta, node_id, concept=None, type_=None):
    """Get direct neighbors, optionally filtered by concept/type."""
    node_id = str(node_id)
    if node_id not in graph:
        raise ValueError(f"node {node_id} not found")
    return [
        n for n in graph[node_id]
        if _matches(meta, n, concept=concept, type_=type_)
    ]


def subgraph(graph, meta, start_id, depth=1, concept=None, type_=None):
    """BFS traversal up to depth, optionally filtered by concept/type.
    The start node is always included regardless of filters."""
    start_id = str(start_id)
    if start_id not in graph:
        raise ValueError(f"node {start_id} not found")

    visited = {start_id}
    queue = deque([(start_id, 0)])
    result = []

    while queue:
        node, d = queue.popleft()
        if d > depth:
            continue

        if node == start_id or _matches(meta, node, concept=concept, type_=type_):
            result.append(node)

        for neigh in graph.get(node, []):
            if neigh not in visited:
                visited.add(neigh)
                queue.append((neigh, d + 1))

    return result


def shortest_path(graph, meta, src, dst, concept=None, type_=None):
    """BFS shortest path. When filters are set, intermediate nodes must
    match; destination must also match if filters are set."""
    src, dst = str(src), str(dst)
    if src not in graph:
        raise ValueError(f"source {src} not found")
    if dst not in graph:
        raise ValueError(f"destination {dst} not found")
    if src == dst:
        return [src]

    queue = deque([(src, [src])])
    visited = {src}

    while queue:
        node, path = queue.popleft()
        for neigh in graph.get(node, []):
            if neigh in visited:
                continue
            if concept is not None or type_ is not None:
                if neigh != dst and not _matches(meta, neigh, concept=concept, type_=type_):
                    continue
                if neigh == dst and not _matches(meta, neigh, concept=concept, type_=type_):
                    continue
            if neigh == dst:
                return path + [neigh]
            visited.add(neigh)
            queue.append((neigh, path + [neigh]))

    return []
