"""Fruchterman-Reingold force-directed layout (clean-room implementation).

Reference:
    Fruchterman, T. M. J. & Reingold, E. M. (1991).
    "Graph drawing by force-directed placement."
    Software: Practice and Experience, 21(11), 1129-1164.

The algorithm models nodes as charged particles that repel each other and
edges as springs that attract their endpoints. Repulsive force decays as
``k**2 / d`` and attractive force grows as ``d**2 / k``, where ``k`` is
the ideal node distance and ``d`` is the inter-node distance. A linear
"temperature" cooling schedule limits per-iteration displacement so the
layout settles.

This module was implemented from the paper above. No code from
third-party implementations was consulted.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from ._common import edge_index_array


def apply_fr(
    nodes: List[str],
    edges: Iterable[Tuple[str, str]],
    *,
    pinned: Optional[Dict[str, Tuple[float, float]]] = None,
    iterations: int = 50,
    seed: int = 42,
    scale: float = 800.0,
    center: Tuple[float, float] = (0.0, 0.0),
) -> Dict[str, Tuple[int, int]]:
    """Fruchterman-Reingold layout.

    Args:
        nodes: All node identifiers participating in the layout.
        edges: Iterable of ``(a, b)`` undirected edges. Self-loops and
            edges to unknown nodes are silently dropped.
        pinned: Map of node -> ``(x, y)``. Pinned nodes act as fixed
            anchors during the simulation and are absent from the
            return value.
        iterations: Cooling schedule length.
        seed: Seed for the initial random placement.
        scale: Half-width of the initial random box; also controls
            ``k`` (ideal node distance) via ``k = sqrt(area / n)``
            with area = ``(2 * scale)**2``.
        center: Output offset added to every returned position.

    Returns:
        ``{node: (x, y)}`` for every non-pinned input node.
    """
    pinned = dict(pinned or {})
    n = len(nodes)
    if n == 0:
        return {}

    idx = {nm: i for i, nm in enumerate(nodes)}
    rng = np.random.default_rng(seed)
    pos = rng.uniform(-scale, scale, size=(n, 2))

    pinned_mask = np.zeros(n, dtype=bool)
    for nm, (px, py) in pinned.items():
        i = idx.get(nm)
        if i is not None:
            pos[i] = (float(px), float(py))
            pinned_mask[i] = True

    edge_arr = edge_index_array(nodes, edges)

    area = (2.0 * scale) ** 2
    k = (area / max(n, 1)) ** 0.5
    k_sq = k * k
    t_init = scale / 10.0
    eps = 1e-9

    for it in range(iterations):
        # Repulsion (all pairs)
        delta = pos[:, None, :] - pos[None, :, :]   # (n, n, 2)
        dist_sq = (delta * delta).sum(-1)
        dist = np.sqrt(dist_sq)
        np.fill_diagonal(dist, eps)
        rep_mag = k_sq / dist
        np.fill_diagonal(rep_mag, 0.0)
        unit = delta / dist[..., None]
        disp = (unit * rep_mag[..., None]).sum(axis=1)   # (n, 2)

        # Attraction (per edge)
        if edge_arr.size:
            d = pos[edge_arr[:, 1]] - pos[edge_arr[:, 0]]
            d_norm = np.linalg.norm(d, axis=1, keepdims=True)
            d_norm_safe = np.maximum(d_norm, eps)
            att_mag = (d_norm_safe * d_norm_safe) / k
            att_vec = (d / d_norm_safe) * att_mag
            np.add.at(disp, edge_arr[:, 0], att_vec)
            np.add.at(disp, edge_arr[:, 1], -att_vec)

        # Pinned nodes do not move; clear their displacement
        disp[pinned_mask] = 0.0

        # Limit displacement by temperature t (linearly decaying)
        disp_mag = np.linalg.norm(disp, axis=1, keepdims=True)
        disp_mag_safe = np.maximum(disp_mag, eps)
        t = t_init * (1.0 - it / max(iterations, 1))
        clipped = (disp / disp_mag_safe) * np.minimum(disp_mag, t)
        pos += clipped

    cx, cy = center
    out: Dict[str, Tuple[int, int]] = {}
    for nm in nodes:
        if nm in pinned:
            continue
        i = idx[nm]
        out[nm] = (int(round(pos[i, 0] + cx)), int(round(pos[i, 1] + cy)))
    return out
