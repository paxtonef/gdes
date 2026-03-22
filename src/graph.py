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


# ── V1.9: Advanced queries ────────────────────────────────────────────────────

def detect_cycles(graph):
    """
    Detect cycles in a directed graph using DFS with colour marking.
    Returns a list of cycles, each cycle is a list of node ids.
    An empty list means the graph is a DAG.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    colour = {node: WHITE for node in graph}
    cycles = []

    def dfs(node, path):
        colour[node] = GRAY
        for neigh in graph.get(node, []):
            if neigh not in colour:
                continue  # dangling ref, skip
            if colour[neigh] == GRAY:
                # found a cycle — extract it from path
                cycle_start = path.index(neigh)
                cycles.append(path[cycle_start:] + [neigh])
            elif colour[neigh] == WHITE:
                dfs(neigh, path + [neigh])
        colour[node] = BLACK

    for node in list(graph.keys()):
        if colour[node] == WHITE:
            dfs(node, [node])

    return cycles


def validate_chain(graph, meta, src, dst):
    """
    Validate that a directed path exists from src to dst and return
    a report dict with: valid, path, hops, concepts_traversed.
    """
    src, dst = str(src), str(dst)

    if src not in graph:
        return {"valid": False, "error": f"source {src} not found", "path": []}
    if dst not in graph:
        return {"valid": False, "error": f"destination {dst} not found", "path": []}

    # directed BFS (follow edges as-is, no undirected expansion)
    queue = deque([(src, [src])])
    visited = {src}

    while queue:
        node, path = queue.popleft()
        for neigh in graph.get(node, []):
            if neigh == dst:
                full_path = path + [neigh]
                concepts = [meta.get(n, {}).get("concept") for n in full_path]
                return {
                    "valid": True,
                    "path": full_path,
                    "hops": len(full_path) - 1,
                    "concepts_traversed": concepts,
                }
            if neigh not in visited:
                visited.add(neigh)
                queue.append((neigh, path + [neigh]))

    return {
        "valid": False,
        "error": f"no directed path from {src} to {dst}",
        "path": [],
    }


def connected_components(graph):
    """
    Find weakly connected components (treats directed edges as undirected).
    Returns a list of components, each component is a sorted list of node ids.
    Largest component first.
    """
    # build undirected adjacency
    undirected = {node: set() for node in graph}
    for node, neighbours in graph.items():
        for neigh in neighbours:
            if neigh in undirected:
                undirected[node].add(neigh)
                undirected[neigh].add(node)

    visited = set()
    components = []

    for start in graph:
        if start in visited:
            continue
        # BFS
        component = []
        queue = deque([start])
        visited.add(start)
        while queue:
            node = queue.popleft()
            component.append(node)
            for neigh in undirected.get(node, []):
                if neigh not in visited:
                    visited.add(neigh)
                    queue.append(neigh)
        components.append(sorted(component))

    # largest first
    components.sort(key=len, reverse=True)
    return components
