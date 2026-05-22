"""Geometric layout placement (grid / circle / random / radial) + topology
dispatch.

Pure functions: each takes node keys plus graph data and returns a
``{key: (x, y)}`` dict of NEW positions. Callers merge the result into their
own position store. Nothing here depends on the builder — this keeps all
layout math in one place, out of the serializer.
"""
from __future__ import annotations

import math
import random
from typing import Dict, List, Tuple

from .fa2 import apply_forceatlas2
from .fr import apply_fr
from .tree import apply_tree

_Pos = Dict[str, Tuple[int, int]]


def place_grid(auto_keys: List[str], cx: int, cy: int, scale: float) -> _Pos:
    n = len(auto_keys)
    out: _Pos = {}
    cols = math.ceil(math.sqrt(n))
    spacing = int(round(200 * scale))
    for i, key in enumerate(auto_keys):
        row_i, col_i = divmod(i, cols)
        x = cx + col_i * spacing - (cols - 1) * spacing // 2
        y = cy + row_i * spacing - ((n // cols) - 1) * spacing // 2
        out[key] = (x, y)
    return out


def place_circle(auto_keys: List[str], cx: int, cy: int, scale: float) -> _Pos:
    n = len(auto_keys)
    out: _Pos = {}
    radius = max(150, n * 35) * scale
    for i, key in enumerate(auto_keys):
        angle = 2 * math.pi * i / n
        x = cx + int(radius * math.cos(angle))
        y = cy + int(radius * math.sin(angle))
        out[key] = (x, y)
    return out


def place_random(auto_keys: List[str], cx: int, cy: int, scale: float) -> _Pos:
    out: _Pos = {}
    rng = random.Random(42)
    extent = int(round(400 * scale))
    for key in auto_keys:
        x = cx + rng.randint(-extent, extent)
        y = cy + rng.randint(-extent, extent)
        out[key] = (x, y)
    return out


def place_topology(mode: str, all_keys: List[str], edges: List[Tuple[str, str]],
                   pinned: Dict[str, Tuple[float, float]], cx: int, cy: int,
                   scale: float) -> _Pos:
    """Dispatch to a topology-aware engine (``fr`` / ``forceatlas2`` / ``tree``).

    Pinned positions are passed through as fixed anchors; only non-pinned nodes
    are returned by the engines.
    """
    if mode == 'fr':
        return apply_fr(all_keys, edges, pinned=pinned, center=(cx, cy),
                        scale=800.0 * scale)
    if mode == 'forceatlas2':
        return apply_forceatlas2(all_keys, edges, pinned=pinned, center=(cx, cy),
                                 scale=60.0 * scale)
    return apply_tree(all_keys, edges, pinned=pinned, center=(cx, cy),
                      x_spacing=160.0 * scale, y_spacing=200.0 * scale)


def place_radial(auto_keys: List[str], all_keys: List[str],
                 edges: List[Tuple[str, str]], cx: int, cy: int,
                 scale: float) -> _Pos:
    """Hub-and-spokes layout with compaction.

    Builds the entity adjacency graph from *edges*, identifies hubs
    (degree >= 2), attaches each non-hub leaf to its highest-degree hub
    neighbour, then places hubs on a ring with leaves on an outward-facing arc.
    Isolated entities (degree 0, or no hub neighbour in *auto_keys*) go in a
    grid below the layout. Adjacency spans *all_keys* so a leaf attached to a
    manually-positioned entity still counts as having a neighbour.
    """
    out: _Pos = {}
    adj: Dict[str, set] = {k: set() for k in all_keys}
    for a, b in edges:
        if a in adj and b in adj:
            adj[a].add(b)
            adj[b].add(a)

    degrees = {k: len(adj[k]) for k in auto_keys}

    hubs = [k for k in auto_keys if degrees[k] >= 2]
    hubs.sort(key=lambda k: (-degrees[k], k))
    hub_set = set(hubs)

    leaf_to_hub: Dict[str, str] = {}
    isolated: List[str] = []
    for k in auto_keys:
        if k in hub_set:
            continue
        hub_neighbours = [n for n in adj[k] if n in hub_set]
        if hub_neighbours:
            leaf_to_hub[k] = max(hub_neighbours, key=lambda h: (degrees[h], h))
        else:
            isolated.append(k)

    hub_leaves: Dict[str, List[str]] = {h: [] for h in hubs}
    for leaf, hub in leaf_to_hub.items():
        hub_leaves[hub].append(leaf)

    # ── Place hubs ────────────────────────────────────────────────────
    n_hubs = len(hubs)
    hub_ring_radius = (
        0 if n_hubs <= 1 else max(260, n_hubs * 70) * scale
    )
    hub_pos: Dict[str, Tuple[int, int]] = {}

    if n_hubs == 1:
        h = hubs[0]
        hub_pos[h] = (cx, cy)
        out[h] = (cx, cy)
    else:
        for i, h in enumerate(hubs):
            a = 2 * math.pi * i / n_hubs
            hx = cx + int(hub_ring_radius * math.cos(a))
            hy = cy + int(hub_ring_radius * math.sin(a))
            hub_pos[h] = (hx, hy)
            out[h] = (hx, hy)

    # ── Place leaves on outward-facing arc per hub ────────────────────
    for h, leaves in hub_leaves.items():
        if not leaves:
            continue
        hx, hy = hub_pos[h]
        n_leaves = len(leaves)
        leaf_radius = max(110, 25 + 14 * n_leaves) * scale

        if n_hubs == 1:
            # Full circle around lone hub
            for j, leaf in enumerate(leaves):
                a = 2 * math.pi * j / n_leaves
                lx = hx + int(leaf_radius * math.cos(a))
                ly = hy + int(leaf_radius * math.sin(a))
                out[leaf] = (lx, ly)
        else:
            # Outward direction = vector from chart center to hub
            base_angle = math.atan2(hy - cy, hx - cx)
            arc_span = math.pi  # 180° fan facing outward
            if n_leaves == 1:
                angles = [base_angle]
            else:
                angles = [
                    base_angle - arc_span / 2 + arc_span * j / (n_leaves - 1)
                    for j in range(n_leaves)
                ]
            for j, leaf in enumerate(leaves):
                a = angles[j]
                lx = hx + int(leaf_radius * math.cos(a))
                ly = hy + int(leaf_radius * math.sin(a))
                out[leaf] = (lx, ly)

    # ── Place isolated entities in a grid below the layout ────────────
    if isolated:
        cols = math.ceil(math.sqrt(len(isolated)))
        spacing = int(round(160 * scale))
        y_offset = int(round(hub_ring_radius + 320 * scale))
        for i, key in enumerate(isolated):
            row_i, col_i = divmod(i, cols)
            x = cx + col_i * spacing - (cols - 1) * spacing // 2
            y = cy + y_offset + row_i * spacing
            out[key] = (x, y)

    return out


def place(mode: str, *, all_keys: List[str], auto_keys: List[str],
          edges: List[Tuple[str, str]], pinned: Dict[str, Tuple[float, float]],
          center: Tuple[int, int], scale: float) -> _Pos:
    """Compute NEW positions for *auto_keys* under *mode*.

    Geometric modes (grid/circle/radial/random) position only *auto_keys*;
    topology modes treat *pinned* as fixed anchors and return the rest.
    Unknown modes fall through to ``random`` (matching the historical default).
    """
    from . import normalize_arrange
    mode = normalize_arrange(mode)
    cx, cy = center
    if mode == 'grid':
        return place_grid(auto_keys, cx, cy, scale)
    if mode == 'circle':
        return place_circle(auto_keys, cx, cy, scale)
    if mode == 'radial':
        return place_radial(auto_keys, all_keys, edges, cx, cy, scale)
    if mode in ('fr', 'forceatlas2', 'tree'):
        return place_topology(mode, all_keys, edges, pinned, cx, cy, scale)
    return place_random(auto_keys, cx, cy, scale)
