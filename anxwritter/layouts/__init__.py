"""Topology-aware layout algorithms for entity positioning.

Each algorithm has the same signature shape::

    apply_X(nodes, edges, *, pinned, ...) -> Dict[str, (int, int)]

``pinned`` maps a subset of node identifiers to fixed ``(x, y)``
positions. The returned dict contains only non-pinned nodes. Pinned
positions are respected: force-directed algorithms treat them as fixed
anchors during simulation; tree layout keeps them at their pinned
coordinates.

All three algorithms are clean-room implementations from the cited
papers — see each module's docstring for the reference.
"""
from .fa2 import apply_forceatlas2
from .fr import apply_fr
from .tree import apply_tree

# Map any user-supplied arrange string to its canonical key. Keys are
# normalized via ``_canon`` (lowercase, spaces/dashes -> underscores).
_ALIASES: dict = {
    # Force-directed (Fruchterman-Reingold)
    'fr': 'fr',
    'fruchterman_reingold': 'fr',
    # ForceAtlas2
    'forceatlas2': 'forceatlas2',
    'force_atlas_2': 'forceatlas2',
    'force_atlas2': 'forceatlas2',
    'fa2': 'forceatlas2',
    # Tidy tree (Reingold-Tilford family)
    'tree': 'tree',
    'reingold_tilford': 'tree',
    'tidy_tree': 'tree',
    # Existing geometric modes (passthrough)
    'radial': 'radial',
    'circle': 'circle',
    'grid': 'grid',
    'random': 'random',
}


def _canon(s: str) -> str:
    return (s or '').strip().lower().replace('-', '_').replace(' ', '_')


def normalize_arrange(mode: str) -> str:
    """Return the canonical arrange key for *mode*, or *mode* itself
    unchanged when no alias matches (preserving the existing
    fall-through-to-random behaviour for unknown values).
    """
    if not mode:
        return mode
    return _ALIASES.get(_canon(mode), mode)


__all__ = [
    'apply_fr',
    'apply_forceatlas2',
    'apply_tree',
    'normalize_arrange',
]
