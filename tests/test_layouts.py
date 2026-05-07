"""Tests for the topology-aware layouts: FR, ForceAtlas2, and tidy tree.

Covers determinism, pinned-respect, alias normalization, hand-checked
small-graph expectations, and integration via ``ANXChart`` settings.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from anxwritter import ANXChart
from anxwritter.layouts import (
    apply_forceatlas2,
    apply_fr,
    apply_tree,
    normalize_arrange,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def _positions(chart: ANXChart) -> dict:
    """Return ``{label -> (x, y)}`` from emitted XML."""
    root = ET.fromstring(chart.to_xml())
    out = {}
    for ci in root.findall('.//ChartItem'):
        label = ci.get('Label')
        if not label:
            continue
        x = int(ci.get('XPosition', '0'))
        end = ci.find('.//End')
        y = int(end.get('Y', '0')) if end is not None else 0
        out[label] = (x, y)
    return out


def _hub_spoke(mode: str, n_leaves: int = 5, **pin_hub) -> ANXChart:
    c = ANXChart(settings={'extra_cfg': {'arrange': mode}})
    c.add_icon(id='hub', type='T', **pin_hub)
    for i in range(n_leaves):
        nm = f'leaf{i}'
        c.add_icon(id=nm, type='T')
        c.add_link(from_id='hub', to_id=nm, type='X')
    return c


def _two_clusters(mode: str) -> ANXChart:
    """Two 4-cliques connected by one bridge edge."""
    c = ANXChart(settings={'extra_cfg': {'arrange': mode}})
    for n in ('A1', 'A2', 'A3', 'A4', 'B1', 'B2', 'B3', 'B4'):
        c.add_icon(id=n, type='T')
    a_clique = [('A1', 'A2'), ('A1', 'A3'), ('A1', 'A4'),
                ('A2', 'A3'), ('A2', 'A4'), ('A3', 'A4')]
    b_clique = [('B1', 'B2'), ('B1', 'B3'), ('B1', 'B4'),
                ('B2', 'B3'), ('B2', 'B4'), ('B3', 'B4')]
    for f, t in a_clique + b_clique:
        c.add_link(from_id=f, to_id=t, type='X')
    c.add_link(from_id='A1', to_id='B1', type='X')   # bridge
    return c


# ── Alias normalization ────────────────────────────────────────────────────


@pytest.mark.parametrize("inp,expected", [
    ('fr', 'fr'),
    ('FR', 'fr'),
    ('Fruchterman_Reingold', 'fr'),
    ('fruchterman-reingold', 'fr'),
    ('forceatlas2', 'forceatlas2'),
    ('FORCEATLAS2', 'forceatlas2'),
    ('fa2', 'forceatlas2'),
    ('Force Atlas 2', 'forceatlas2'),
    ('force-atlas-2', 'forceatlas2'),
    ('tree', 'tree'),
    ('Reingold-Tilford', 'tree'),
    ('tidy_tree', 'tree'),
    ('radial', 'radial'),
    ('grid', 'grid'),
    ('circle', 'circle'),
    ('random', 'random'),
])
def test_alias_normalization(inp, expected):
    assert normalize_arrange(inp) == expected


def test_unknown_arrange_passes_through():
    """Unknown values fall through unchanged (existing behaviour)."""
    assert normalize_arrange('totally_made_up') == 'totally_made_up'


def test_normalize_empty_passes_through():
    assert normalize_arrange('') == ''
    assert normalize_arrange(None) is None


# ── Determinism ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ['fr', 'forceatlas2', 'tree'])
def test_determinism_same_input_same_output(mode):
    p1 = _positions(_hub_spoke(mode))
    p2 = _positions(_hub_spoke(mode))
    assert p1 == p2


@pytest.mark.parametrize("mode", ['fr', 'forceatlas2', 'tree'])
def test_determinism_two_clusters(mode):
    p1 = _positions(_two_clusters(mode))
    p2 = _positions(_two_clusters(mode))
    assert p1 == p2


@pytest.mark.parametrize("mode", ['fr', 'forceatlas2'])
def test_force_directed_seeded(mode):
    """Different seeds (via direct call) produce different layouts."""
    fn = apply_fr if mode == 'fr' else apply_forceatlas2
    nodes = ['a', 'b', 'c', 'd', 'e']
    edges = [('a', 'b'), ('b', 'c'), ('c', 'd'), ('d', 'e')]
    p1 = fn(nodes, edges, seed=1)
    p2 = fn(nodes, edges, seed=2)
    assert p1 != p2


# ── Pinned-respect ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ['fr', 'forceatlas2', 'tree'])
def test_pinned_position_preserved_through_chart(mode):
    c = _hub_spoke(mode, n_leaves=4, x=999, y=888)
    pos = _positions(c)
    assert pos['hub'] == (999, 888)


@pytest.mark.parametrize("mode", ['fr', 'forceatlas2'])
def test_pinned_anchors_via_direct_call(mode):
    fn = apply_fr if mode == 'fr' else apply_forceatlas2
    nodes = ['hub', 'a', 'b', 'c']
    edges = [('hub', 'a'), ('hub', 'b'), ('hub', 'c')]
    out = fn(nodes, edges, pinned={'hub': (1234, 5678)})
    assert 'hub' not in out
    assert {'a', 'b', 'c'} == set(out.keys())


def test_tree_pinned_excluded_from_output():
    """Tree layout omits pinned nodes from output dict (their positions
    are kept by the chart, untouched)."""
    out = apply_tree(
        ['root', 'a', 'b'],
        [('root', 'a'), ('root', 'b')],
        pinned={'root': (10, 20)},
    )
    assert 'root' not in out
    assert {'a', 'b'} == set(out.keys())


# ── Topology correctness ───────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ['fr', 'forceatlas2'])
def test_force_directed_separates_clusters(mode):
    """In a 2-cluster bridge graph, every A node should be closer to
    every other A node than to every B node (with the bridge as the
    only A-B edge)."""
    pos = _positions(_two_clusters(mode))
    a_set = {'A1', 'A2', 'A3', 'A4'}
    b_set = {'B1', 'B2', 'B3', 'B4'}

    # Mean-distance check — clusters are clearly separated
    def mean_dist(group_a, group_b):
        ds = []
        for a in group_a:
            for b in group_b:
                if a == b:
                    continue
                dx = pos[a][0] - pos[b][0]
                dy = pos[a][1] - pos[b][1]
                ds.append((dx * dx + dy * dy) ** 0.5)
        return sum(ds) / len(ds)

    aa = mean_dist(a_set, a_set)
    bb = mean_dist(b_set, b_set)
    ab = mean_dist(a_set, b_set)
    assert ab > aa, f"{mode}: A-B mean ({ab:.0f}) should exceed A-A ({aa:.0f})"
    assert ab > bb, f"{mode}: A-B mean ({ab:.0f}) should exceed B-B ({bb:.0f})"


def test_tree_root_above_leaves():
    """In a hub-spoke laid out as tree, hub (root) sits above leaves
    in ANB's coordinate system (y increases downward)."""
    pos = _positions(_hub_spoke('tree', n_leaves=4))
    hub_y = pos['hub'][1]
    for k in ('leaf0', 'leaf1', 'leaf2', 'leaf3'):
        assert pos[k][1] > hub_y, f"{k} should be below hub in tree layout"


def test_tree_balanced_binary_layout():
    """Pin the desired root, then check the remaining nodes layer by depth."""
    out = apply_tree(
        ['r', 'l', 'rr', 'll', 'lr', 'rl', 'rrr'],
        [('r', 'l'), ('r', 'rr'),
         ('l', 'll'), ('l', 'lr'),
         ('rr', 'rl'), ('rr', 'rrr')],
        pinned={'r': (0, 0)},   # forces 'r' as the BFS root
    )
    # 'r' is excluded from output; check the children/grandchildren bands.
    ys = {k: v[1] for k, v in out.items()}
    assert ys['l'] == ys['rr']                          # depth 1 band
    assert ys['ll'] == ys['lr'] == ys['rl'] == ys['rrr']  # depth 2 band
    assert ys['l'] < ys['ll']                            # depth 1 above depth 2


def test_tree_chain_pinned_root():
    """A linear chain with 'a' pinned as root spreads y monotonically."""
    out = apply_tree(
        ['a', 'b', 'c', 'd', 'e'],
        [('a', 'b'), ('b', 'c'), ('c', 'd'), ('d', 'e')],
        pinned={'a': (0, 0)},
    )
    ys = [out[n][1] for n in ('b', 'c', 'd', 'e')]
    assert ys == sorted(ys)
    assert len(set(ys)) == 4   # one band per depth (a is excluded from output)


def test_tree_picks_highest_degree_as_root():
    """Without a pin, BFS picks the highest-degree node as root.

    For a chain a-b-c-d-e, that's the alphabetically-first node among
    the degree-2 set ('b'), and the tree extends in two directions.
    """
    out = apply_tree(
        ['a', 'b', 'c', 'd', 'e'],
        [('a', 'b'), ('b', 'c'), ('c', 'd'), ('d', 'e')],
    )
    # 'b' at depth 0; 'a' and 'c' at depth 1; 'd' at depth 2; 'e' at depth 3
    ys = {k: v[1] for k, v in out.items()}
    assert ys['a'] == ys['c']          # both depth 1
    assert ys['b'] < ys['a']           # root above
    assert ys['a'] < ys['d'] < ys['e'] # increasing depth


# ── Edge cases ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fn", [apply_fr, apply_forceatlas2, apply_tree])
def test_empty_graph(fn):
    assert fn([], []) == {}


@pytest.mark.parametrize("fn", [apply_fr, apply_forceatlas2, apply_tree])
def test_single_node(fn):
    out = fn(['only'], [])
    assert set(out) == {'only'}


@pytest.mark.parametrize("fn", [apply_fr, apply_forceatlas2, apply_tree])
def test_self_loops_dropped(fn):
    """Self-loops are silently dropped without crashing."""
    out = fn(['a', 'b'], [('a', 'a'), ('a', 'b'), ('b', 'b')])
    assert set(out) == {'a', 'b'}


@pytest.mark.parametrize("fn", [apply_fr, apply_forceatlas2, apply_tree])
def test_unknown_endpoint_dropped(fn):
    """Edges referencing unknown nodes are silently dropped."""
    out = fn(['a', 'b'], [('a', 'ghost'), ('a', 'b')])
    assert set(out) == {'a', 'b'}


@pytest.mark.parametrize("mode", ['fr', 'forceatlas2', 'tree'])
def test_disconnected_components(mode):
    """A graph with two unconnected components still places everything."""
    c = ANXChart(settings={'extra_cfg': {'arrange': mode}})
    for n in ('A', 'B', 'C', 'X', 'Y'):
        c.add_icon(id=n, type='T')
    c.add_link(from_id='A', to_id='B', type='X')
    c.add_link(from_id='B', to_id='C', type='X')
    c.add_link(from_id='X', to_id='Y', type='X')
    pos = _positions(c)
    assert {'A', 'B', 'C', 'X', 'Y'} <= set(pos)


@pytest.mark.parametrize("mode", ['fr', 'forceatlas2', 'tree'])
def test_isolated_nodes(mode):
    """Nodes with no edges still get a position."""
    c = ANXChart(settings={'extra_cfg': {'arrange': mode}})
    for n in ('a', 'b', 'lone1', 'lone2'):
        c.add_icon(id=n, type='T')
    c.add_link(from_id='a', to_id='b', type='X')
    pos = _positions(c)
    assert {'a', 'b', 'lone1', 'lone2'} <= set(pos)


# ── ForceAtlas2 knobs ──────────────────────────────────────────────────────


def test_fa2_lin_log_changes_output():
    """LinLog mode produces a different layout than the default linear."""
    nodes = ['a', 'b', 'c', 'd', 'e', 'f']
    edges = [('a', 'b'), ('b', 'c'), ('a', 'c'),  # clique 1
             ('d', 'e'), ('e', 'f'), ('d', 'f'),  # clique 2
             ('c', 'd')]
    p_lin = apply_forceatlas2(nodes, edges, lin_log=False)
    p_log = apply_forceatlas2(nodes, edges, lin_log=True)
    assert p_lin != p_log


def test_fa2_strong_gravity_pulls_inward():
    """Strong gravity tightens isolated layout toward origin."""
    nodes = ['a', 'b', 'c']
    edges = [('a', 'b')]   # c isolated
    p_normal = apply_forceatlas2(nodes, edges, gravity=1.0)
    p_strong = apply_forceatlas2(nodes, edges, gravity=10.0, strong_gravity=True)

    def mean_dist(p):
        return sum((x * x + y * y) ** 0.5 for x, y in p.values()) / len(p)
    assert mean_dist(p_strong) < mean_dist(p_normal)


# ── Integration: backward-compat invariants ────────────────────────────────


def test_existing_modes_unchanged():
    """Adding new modes did not alter the geometric ones."""
    for mode in ('radial', 'circle', 'grid', 'random'):
        c = _hub_spoke(mode, n_leaves=3)
        pos = _positions(c)
        assert {'hub', 'leaf0', 'leaf1', 'leaf2'} <= set(pos)


def test_default_arrange_still_radial():
    """Sanity: when no arrange is set, radial runs (not random)."""
    c = ANXChart()
    c.add_icon(id='hub', type='T')
    c.add_icon(id='a', type='T')
    c.add_icon(id='b', type='T')
    c.add_link(from_id='hub', to_id='a', type='X')
    c.add_link(from_id='hub', to_id='b', type='X')
    pos = _positions(c)
    # Lone hub should be at origin under radial
    assert pos['hub'] == (0, 0)


# ── Perf marker (excluded from default runs) ───────────────────────────────


@pytest.mark.perf
@pytest.mark.parametrize("mode", ['fr', 'forceatlas2', 'tree'])
def test_layout_scale_1k_nodes(mode):
    """1000 nodes, 2000 edges should complete under 30s on any modern box."""
    import time
    c = ANXChart(settings={'extra_cfg': {'arrange': mode}})
    for i in range(1000):
        c.add_icon(id=f'n{i}', type='T')
    # Random-ish edges (deterministic via seed)
    import random as _r
    rng = _r.Random(42)
    for _ in range(2000):
        a = rng.randint(0, 999)
        b = rng.randint(0, 999)
        if a != b:
            c.add_link(from_id=f'n{a}', to_id=f'n{b}', type='X')
    t0 = time.perf_counter()
    c.to_xml()
    elapsed = time.perf_counter() - t0
    assert elapsed < 30.0, f"{mode} on 1k took {elapsed:.1f}s"
