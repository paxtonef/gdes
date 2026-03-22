from collections import deque
from typing import Dict, List, Set, Optional


def build_adjacency(artifacts):
    """
    artifacts: list of dicts with 'id' and 'related_to'
    returns: dict {id: [neighbors]}
    """
    graph = {}
    for a in artifacts:
        node = str(a["id"])
        refs = [str(r) for r in a.get("related_to", []) or []]
        graph[node] = refs
    return graph


def neighbors(graph, node_id):
    """Get direct neighbors of a node"""
    node_id = str(node_id)
    if node_id not in graph:
        raise ValueError(f"node {node_id} not found")
    return graph[node_id]


def subgraph(graph, start_id, depth=1):
    """BFS traversal up to depth"""
    start_id = str(start_id)
    if start_id not in graph:
        raise ValueError(f"node {start_id} not found")

    visited = set([start_id])
    queue = deque([(start_id, 0)])
    result = []

    while queue:
        node, d = queue.popleft()
        if d > depth:
            continue

        result.append(node)

        for neigh in graph.get(node, []):
            if neigh not in visited:
                visited.add(neigh)
                queue.append((neigh, d + 1))

    return result


def shortest_path(graph, src, dst):
    """Find shortest path between two nodes (BFS)"""
    src, dst = str(src), str(dst)

    if src not in graph:
        raise ValueError(f"source {src} not found")
    if dst not in graph:
        raise ValueError(f"destination {dst} not found")

    queue = deque([(src, [src])])
    visited = set([src])

    while queue:
        node, path = queue.popleft()

        if node == dst:
            return path

        for neigh in graph.get(node, []):
            if neigh not in visited:
                visited.add(neigh)
                queue.append((neigh, path + [neigh]))

    return []  # no path
