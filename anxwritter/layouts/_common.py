"""Shared helpers for layout algorithms."""
from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple

import numpy as np


def build_adjacency(
    nodes: List[str],
    edges: Iterable[Tuple[str, str]],
) -> Dict[str, Set[str]]:
    """Undirected adjacency dict, ignoring self-loops and unknown endpoints."""
    adj: Dict[str, Set[str]] = {n: set() for n in nodes}
    for a, b in edges:
        if a == b:
            continue
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)
    return adj


def edge_index_array(
    nodes: List[str],
    edges: Iterable[Tuple[str, str]],
) -> np.ndarray:
    """``(E, 2)`` int array of edge endpoints (indexed into ``nodes``)."""
    idx = {n: i for i, n in enumerate(nodes)}
    pairs: List[Tuple[int, int]] = []
    seen: Set[Tuple[int, int]] = set()
    for a, b in edges:
        if a == b:
            continue
        ia = idx.get(a)
        ib = idx.get(b)
        if ia is None or ib is None:
            continue
        key = (ia, ib) if ia < ib else (ib, ia)
        if key in seen:
            continue
        seen.add(key)
        pairs.append((ia, ib))
    if not pairs:
        return np.zeros((0, 2), dtype=np.int64)
    return np.asarray(pairs, dtype=np.int64)


def degrees_from_edges(n: int, edge_arr: np.ndarray) -> np.ndarray:
    """Degree vector ``(n,)`` from an ``(E, 2)`` edge array."""
    deg = np.zeros(n, dtype=np.float64)
    if edge_arr.size:
        np.add.at(deg, edge_arr[:, 0], 1.0)
        np.add.at(deg, edge_arr[:, 1], 1.0)
    return deg
