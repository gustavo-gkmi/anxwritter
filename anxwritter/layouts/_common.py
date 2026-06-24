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


def repulsion_forces(
    pos: np.ndarray,
    weight,            # Optional[np.ndarray] — None = uniform (no mass weighting)
    strength: float,
    eps_sq: float,
    *,
    tile_bytes: float = 128e6,
    tile_threshold: int = 2048,
) -> np.ndarray:
    """All-pairs repulsion as a split-coordinate sum, optionally row-tiled.

    The per-pair force on ``i`` from ``j`` is ``(x_i - x_j) * C_ij`` with
    ``C_ij = strength * weight_i * weight_j / dist²_ij``. Summed over ``j`` this
    is ``x_i * Σ_j C_ij - Σ_j C_ij x_j = x_i * S - (C @ x)`` — only an ``(n, n)``
    coefficient matrix and two mat-vecs, no ``(n, n, 2)`` delta (Tier 1). Pairwise
    squared distance via the Gram identity
    ``‖x_i - x_j‖² = |x_i|² + |x_j|² - 2 x_i·x_j``.

    For ``n > tile_threshold`` the coefficient matrix is built in row blocks
    sized so each tile stays under ``tile_bytes`` (Tier 2). Peak memory becomes
    ``O(block · n)`` instead of ``O(n²)``, so large layouts complete instead of
    hitting a multi-GB allocation. The per-row arithmetic is identical to the
    single-shot path, so the result is unchanged (deterministic, same quality).

    Shared by Fruchterman-Reingold (``weight = None``, ``strength = k²``) and
    ForceAtlas2 (``weight = mass``, ``strength = scaling_ratio``). ``weight=None``
    skips the (n, n) mass outer product entirely. Clean-room: standard linear
    algebra over each algorithm's own published force law.
    """
    n = pos.shape[0]
    sq = np.einsum('ij,ij->i', pos, pos)

    if n <= tile_threshold:
        dist_sq = sq[:, None] + sq[None, :] - 2.0 * (pos @ pos.T)
        np.maximum(dist_sq, eps_sq, out=dist_sq)
        coef = (strength * (weight[:, None] * weight[None, :]) / dist_sq
                if weight is not None else strength / dist_sq)
        np.fill_diagonal(coef, 0.0)
        return pos * coef.sum(axis=1)[:, None] - coef @ pos

    block = max(256, int(tile_bytes / (8.0 * n)))
    forces = np.empty_like(pos)
    for s in range(0, n, block):
        e = min(s + block, n)
        dist_sq = sq[s:e, None] + sq[None, :] - 2.0 * (pos[s:e] @ pos.T)
        np.maximum(dist_sq, eps_sq, out=dist_sq)
        coef = (strength * (weight[s:e, None] * weight[None, :]) / dist_sq
                if weight is not None else strength / dist_sq)
        rows = np.arange(e - s)
        coef[rows, s + rows] = 0.0   # zero the self-pair on each row's diagonal
        forces[s:e] = pos[s:e] * coef.sum(axis=1)[:, None] - coef @ pos
    return forces


def degrees_from_edges(n: int, edge_arr: np.ndarray) -> np.ndarray:
    """Degree vector ``(n,)`` from an ``(E, 2)`` edge array."""
    deg = np.zeros(n, dtype=np.float64)
    if edge_arr.size:
        np.add.at(deg, edge_arr[:, 0], 1.0)
        np.add.at(deg, edge_arr[:, 1], 1.0)
    return deg
