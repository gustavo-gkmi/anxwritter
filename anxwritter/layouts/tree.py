"""Tidy tree layout (clean-room implementation).

Reference:
    Reingold, E. M. & Tilford, J. S. (1981).
    "Tidier drawings of trees."
    IEEE Transactions on Software Engineering, SE-7(2), 223-228.

The original Reingold-Tilford algorithm targets binary trees with the
"thread" trick. This module implements a generalization for n-ary trees
using bottom-up subtree-width allocation followed by top-down position
assignment — the same family of tidy-tree algorithms, with the simpler
allocation rule trading some compactness for implementation clarity.

For graphs that are not trees, a BFS spanning forest is built first;
non-tree edges are ignored for layout purposes (they still appear in
the chart). Disconnected components are laid out independently and
combined left-to-right.

This module was implemented from the paper above. No code from
third-party implementations was consulted.
"""
from __future__ import annotations

import sys
from collections import deque
from typing import Dict, Iterable, List, Optional, Set, Tuple

from ._common import build_adjacency


def apply_tree(
    nodes: List[str],
    edges: Iterable[Tuple[str, str]],
    *,
    pinned: Optional[Dict[str, Tuple[float, float]]] = None,
    x_spacing: float = 160.0,
    y_spacing: float = 200.0,
    center: Tuple[float, float] = (0.0, 0.0),
) -> Dict[str, Tuple[int, int]]:
    """Tidy tree layout.

    Args:
        nodes: All node identifiers participating in the layout.
        edges: Iterable of ``(a, b)`` undirected edges. The spanning
            tree is derived via BFS.
        pinned: Map of node -> ``(x, y)``. Pinned nodes are kept at
            their fixed positions and absent from the return value.
            They are still placed in the spanning tree but their
            computed position is discarded in favour of the pinned one.
        x_spacing: Horizontal distance between leaves.
        y_spacing: Vertical distance between depth levels.
        center: Output offset added to every returned position.

    Returns:
        ``{node: (x, y)}`` for every non-pinned input node.
    """
    pinned = dict(pinned or {})
    if not nodes:
        return {}

    adj = build_adjacency(nodes, edges)
    pinned_set = set(pinned)

    # Pinned nodes preferred as roots; otherwise highest degree first.
    def root_key(name: str):
        return (0 if name in pinned_set else 1, -len(adj[name]), name)

    candidates = sorted(nodes, key=root_key)

    children: Dict[str, List[str]] = {n: [] for n in nodes}
    visited: Set[str] = set()
    roots: List[str] = []
    for r in candidates:
        if r in visited:
            continue
        roots.append(r)
        visited.add(r)
        q = deque([r])
        while q:
            u = q.popleft()
            for v in sorted(adj[u]):
                if v not in visited:
                    visited.add(v)
                    children[u].append(v)
                    q.append(v)

    # Iterative subtree-width and depth (avoids recursion limits on
    # deep chains).
    subtree_width: Dict[str, int] = {}
    depth: Dict[str, int] = {}

    # Post-order traversal for widths
    sys_recursion = sys.getrecursionlimit()
    if len(nodes) + 100 > sys_recursion:
        sys.setrecursionlimit(len(nodes) + 1000)

    order: List[str] = []
    for r in roots:
        stack: List[Tuple[str, int]] = [(r, 0)]
        depth[r] = 0
        post: List[str] = []
        while stack:
            node, child_i = stack.pop()
            if child_i == 0:
                post.append(node)
            kids = children[node]
            if child_i < len(kids):
                stack.append((node, child_i + 1))
                child = kids[child_i]
                depth[child] = depth[node] + 1
                stack.append((child, 0))
        # post is pre-order; reverse for post-order width computation
        order.extend(reversed(post))

    for node in order:
        kids = children[node]
        if not kids:
            subtree_width[node] = 1
        else:
            subtree_width[node] = max(sum(subtree_width[c] for c in kids), 1)

    # Top-down x assignment: each subtree gets a left edge in "cells",
    # node centred over its children (or over its own cell if leaf).
    raw_pos: Dict[str, Tuple[float, float]] = {}
    cursor = 0
    for r in roots:
        # Place children left-to-right; we need post-order to centre
        # parents after children placed. Use explicit two-phase walk.
        order_lr: List[Tuple[str, int]] = []
        sub_stack: List[Tuple[str, int]] = [(r, cursor)]
        while sub_stack:
            node, left = sub_stack.pop()
            order_lr.append((node, left))
            child_left = left
            for c in children[node]:
                sub_stack.append((c, child_left))
                child_left += subtree_width[c]
        # Place leaves first (post-order) so parents can centre over
        # already-placed children.
        for node, left in reversed(order_lr):
            kids = children[node]
            if not kids:
                x = (left + 0.5) * x_spacing
            else:
                xs = [raw_pos[c][0] for c in kids]
                x = (min(xs) + max(xs)) / 2.0
            raw_pos[node] = (x, depth[node] * y_spacing)
        cursor += subtree_width[r]

    if not raw_pos:
        return {}

    xs = [p[0] for p in raw_pos.values()]
    ys = [p[1] for p in raw_pos.values()]
    mid_x = (min(xs) + max(xs)) / 2.0
    mid_y = (min(ys) + max(ys)) / 2.0

    cx, cy = center
    out: Dict[str, Tuple[int, int]] = {}
    for nm in nodes:
        if nm in pinned:
            continue
        x, y = raw_pos[nm]
        out[nm] = (int(round(x - mid_x + cx)), int(round(y - mid_y + cy)))
    return out
