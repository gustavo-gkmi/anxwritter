"""ForceAtlas2 layout (clean-room implementation).

Reference:
    Jacomy, M., Venturini, T., Heymann, S., & Bastian, M. (2014).
    "ForceAtlas2, a Continuous Graph Layout Algorithm for Handy Network
    Visualization Designed for the Gephi Software."
    PLOS ONE 9(6): e98679.
    https://doi.org/10.1371/journal.pone.0098679
    Open access (CC-BY).

The algorithm uses linear repulsion weighted by node degree (mass),
linear attraction (or LinLog), and per-node gravity to keep components
from drifting apart. The paper's swinging-based adaptive global speed
is replaced here with a simpler linearly-decaying step-size schedule —
the cluster topology of the resulting layout matches the paper's
description; only the per-iteration dynamics differ.

This module was implemented from the paper above. No code from
third-party implementations was consulted.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from ._common import degrees_from_edges, edge_index_array


def apply_forceatlas2(
    nodes: List[str],
    edges: Iterable[Tuple[str, str]],
    *,
    pinned: Optional[Dict[str, Tuple[float, float]]] = None,
    iterations: int = 200,
    seed: int = 42,
    scaling_ratio: float = 2.0,
    gravity: float = 1.0,
    strong_gravity: bool = False,
    lin_log: bool = False,
    dissuade_hubs: bool = False,
    scale: float = 100.0,
    center: Tuple[float, float] = (0.0, 0.0),
) -> Dict[str, Tuple[int, int]]:
    """ForceAtlas2 layout.

    Args:
        nodes: All node identifiers participating in the layout.
        edges: Iterable of ``(a, b)`` undirected edges.
        pinned: Map of node -> ``(x, y)``. Pinned nodes act as fixed
            anchors during the simulation and are absent from the return
            value.
        iterations: Number of simulation steps.
        seed: Seed for the initial random placement.
        scaling_ratio: Repulsion strength multiplier (paper's ``kr``).
            Higher values spread the layout further.
        gravity: Strength of the centripetal pull toward the origin.
            Prevents disconnected components from flying apart.
        strong_gravity: If True, gravity ignores distance (constant
            pull). If False, gravity scales as ``mass / d``.
        lin_log: Use logarithmic attraction (``log(1 + d)``) instead of
            linear (``d``). Pulls clusters tighter and separates them
            more cleanly.
        dissuade_hubs: Divide attraction force at the source by source
            mass — high-degree hubs become less "sticky" and the layout
            reveals authoritative-vs-hub structure.
        scale: Output coordinate multiplier. The simulation runs at unit
            scale (positions roughly in ``[-1, 1]``) and final positions
            are multiplied by ``scale`` to yield pixel coordinates.
            Pinned coordinates are interpreted in pixels and converted to
            sim units on input, so they are preserved exactly.
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
    # Simulation runs at unit scale; multiply by `scale` on output.
    pos = rng.uniform(-1.0, 1.0, size=(n, 2))
    inv_scale = 1.0 / max(scale, 1e-9)

    pinned_mask = np.zeros(n, dtype=bool)
    for nm, (px, py) in pinned.items():
        i = idx.get(nm)
        if i is not None:
            pos[i] = (float(px) * inv_scale, float(py) * inv_scale)
            pinned_mask[i] = True

    edge_arr = edge_index_array(nodes, edges)
    deg = degrees_from_edges(n, edge_arr)
    mass = deg + 1.0                  # (n,) — paper's "mass" is degree + 1

    eps = 1e-9
    base_speed = 0.1

    for it in range(iterations):
        # ── Repulsion (all pairs, mass-weighted) ─────────────────────
        delta = pos[:, None, :] - pos[None, :, :]
        dist = np.sqrt((delta * delta).sum(-1))
        np.fill_diagonal(dist, eps)
        m_outer = mass[:, None] * mass[None, :]
        rep_mag = scaling_ratio * m_outer / dist
        np.fill_diagonal(rep_mag, 0.0)
        unit = delta / dist[..., None]
        forces = (unit * rep_mag[..., None]).sum(axis=1)

        # ── Attraction (per edge) ────────────────────────────────────
        if edge_arr.size:
            d = pos[edge_arr[:, 1]] - pos[edge_arr[:, 0]]
            d_norm = np.linalg.norm(d, axis=1, keepdims=True)
            d_norm_safe = np.maximum(d_norm, eps)
            if lin_log:
                att_mag = np.log1p(d_norm)
            else:
                att_mag = d_norm.copy()
            if dissuade_hubs:
                from_mass = mass[edge_arr[:, 0]][:, None]
                att_mag = att_mag / from_mass
            att_vec = (d / d_norm_safe) * att_mag
            np.add.at(forces, edge_arr[:, 0], att_vec)
            np.add.at(forces, edge_arr[:, 1], -att_vec)

        # ── Gravity (toward origin, per-node) ────────────────────────
        d_origin = np.linalg.norm(pos, axis=1, keepdims=True)
        d_origin_safe = np.maximum(d_origin, eps)
        if strong_gravity:
            grav_mag = gravity * mass[:, None]
        else:
            grav_mag = gravity * mass[:, None] / d_origin_safe
        forces -= (pos / d_origin_safe) * grav_mag

        # Pinned nodes do not move
        forces[pinned_mask] = 0.0

        # Step size: per-node, fully decaying to 0 over iterations.
        # Heavier nodes move slower, matching the paper's traction
        # concept loosely.
        step = base_speed * (1.0 - it / max(iterations, 1))
        pos += forces * (step / mass[:, None])

    cx, cy = center
    out: Dict[str, Tuple[int, int]] = {}
    for nm in nodes:
        if nm in pinned:
            continue
        i = idx[nm]
        out[nm] = (
            int(round(pos[i, 0] * scale + cx)),
            int(round(pos[i, 1] * scale + cy)),
        )
    return out
