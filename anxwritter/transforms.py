"""
Data transformation functions for anxwritter chart building.

These are pure functions that transform resolved entity/link data
without mutating original user objects.
"""
from __future__ import annotations

import colorsys
import json
import math
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from .colors import rgb_to_colorref
from .enums import Representation

if TYPE_CHECKING:
    from .resolved import ResolvedEntity, ResolvedLink, ResolvedAttr
    from .models import Link, GeoMapCfg


def compute_auto_colors(
    entities: List[Any],
) -> Dict[str, Tuple[int, int]]:
    """Compute auto-assigned HSV colors for entities without explicit color.

    Args:
        entities: List of entity objects with id, color, and shade_color attributes.

    Returns:
        Dict mapping entity id to (bg_colorref, fg_colorref) tuple.
        fg_colorref is black (0) for light backgrounds, white (16777215) for dark.
    """
    # Build map of entity id -> explicit color (or None if unset)
    seen: Dict[str, Optional[str]] = {}
    for entity in entities:
        eid = getattr(entity, 'id', None)
        if eid and eid not in seen:
            color_val = getattr(entity, 'color', None) or getattr(entity, 'shade_color', None)
            seen[eid] = str(color_val) if color_val is not None else None

    # Find entities without explicit color
    uncolored = [eid for eid, c in seen.items() if c is None]
    n = len(uncolored)
    if n == 0:
        return {}

    # Assign evenly-spaced HSV hues
    auto_colors: Dict[str, Tuple[int, int]] = {}
    for idx, eid in enumerate(uncolored):
        hue = idx / n if n > 1 else 0.0
        rf, gf, bf = colorsys.hsv_to_rgb(hue, 0.55, 0.90)
        r, g, b = int(rf * 255), int(gf * 255), int(bf * 255)
        bg_colorref = rgb_to_colorref(r, g, b)
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        fg_colorref = 0 if luminance > 128 else 16777215
        auto_colors[eid] = (bg_colorref, fg_colorref)

    return auto_colors


def apply_auto_colors(
    resolved_entities: List['ResolvedEntity'],
    auto_colors: Dict[str, Tuple[int, int]],
) -> None:
    """Apply pre-computed auto-colors to resolved entities.

    Modifies resolved entities in place (no user-object mutation).

    Args:
        resolved_entities: List of ResolvedEntity objects to transform.
        auto_colors: Dict mapping entity id to (bg_colorref, fg_colorref).
    """
    # Representations whose emit path reads `shade_color` (IconShadingColour):
    # Icon, ThemeLine, EventFrame. Others (Box/Circle/TextBlock/Label) use bg_color.
    _SHADE_REPRS = {
        Representation.ICON.value,
        Representation.THEME_LINE.value,
        Representation.EVENT_FRAME.value,
    }
    # ThemeLine and EventFrame have visible borders/lines separate from their
    # shade_color icon tint — setting only shade_color leaves the border at
    # ANB's default, so also set line_color to the same hue.
    _LINE_COLOR_REPRS = {
        Representation.THEME_LINE.value,
        Representation.EVENT_FRAME.value,
    }
    for re in resolved_entities:
        if re.identity in auto_colors and re.representation_style.get('shade_color') is None:
            bg_colorref, fg_colorref = auto_colors[re.identity]
            if re.representation in _SHADE_REPRS:
                re.representation_style['shade_color'] = bg_colorref
            if (re.representation in _LINE_COLOR_REPRS
                    and re.representation_style.get('line_color') is None):
                re.representation_style['line_color'] = bg_colorref
            if re.label_bg_color is None:
                re.label_bg_color = bg_colorref
            if re.label_color is None:
                re.label_color = fg_colorref


def build_entity_color_map(
    resolved_entities: List['ResolvedEntity'],
) -> Dict[str, int]:
    """Build a map of entity identity to resolved shade color.

    Used by link_match_entity_color transform. Entities without a resolved
    shade color are omitted from the map — callers should treat a missing key
    as "no color match available" rather than substituting 0 (black), which
    would silently override any type-level default.
    """
    color_map: Dict[str, int] = {}
    for re in resolved_entities:
        shade = re.representation_style.get('shade_color')
        if shade:
            color_map[re.identity] = shade
    return color_map


def compute_link_offsets(
    links: List['Link'],
    spacing: int = 20,
) -> Dict[int, int]:
    """Compute symmetric arc offsets for parallel links between the same entity pair.

    Args:
        links: List of Link objects with from_id and to_id.
        spacing: Pixel spacing between parallel link arcs.

    Returns:
        Dict mapping link index to computed offset value.
    """
    # Group link indices by entity pair
    pair_link_indices: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for i, link in enumerate(links):
        if link.from_id and link.to_id and link.from_id != link.to_id:
            pair_link_indices[(link.from_id, link.to_id)].append(i)

    # Compute symmetric offsets for each group
    auto_offsets: Dict[int, int] = {}
    for pair, indices in pair_link_indices.items():
        for idx, off in zip(indices, _compute_symmetric_offsets(len(indices), spacing)):
            auto_offsets[idx] = off

    return auto_offsets


def _compute_symmetric_offsets(n: int, spacing: int) -> List[int]:
    """Compute symmetric offsets for n parallel items.

    For even n: ..., -1.5*spacing, -0.5*spacing, +0.5*spacing, +1.5*spacing, ...
    For odd n:  ..., -spacing, 0, +spacing, ...
    """
    if n <= 1:
        return [0] * max(n, 0)
    half = spacing // 2
    if n % 2 == 0:
        result: List[int] = []
        for k in range(n // 2):
            mag = half + k * spacing
            result.append(mag)
            result.append(-mag)
        return result
    else:
        result = [0]
        for k in range(1, (n + 1) // 2):
            mag = k * spacing
            result.append(mag)
            result.append(-mag)
        return result


def apply_link_entity_colors(
    resolved_links: List['ResolvedLink'],
    links: List['Link'],
    entity_color_map: Dict[str, int],
) -> None:
    """Set link line colors to match their to_id entity's color.

    Only applies to links without explicit line_color set.
    Modifies resolved links in place.

    Args:
        resolved_links: List of ResolvedLink objects (same order as links).
        links: Original Link objects to check for explicit line_color.
        entity_color_map: Dict mapping entity id to color (from build_entity_color_map).
    """
    for rl, link in zip(resolved_links, links):
        if link.line_color is None and link.to_id in entity_color_map:
            rl.line_color = entity_color_map[link.to_id]


def apply_link_auto_offsets(
    resolved_links: List['ResolvedLink'],
    links: List['Link'],
    auto_offsets: Dict[int, int],
) -> None:
    """Apply auto-computed offsets to links without explicit offset.

    Args:
        resolved_links: List of ResolvedLink objects.
        links: Original Link objects to check for explicit offset.
        auto_offsets: Dict from compute_link_offsets().
    """
    for i, (rl, link) in enumerate(zip(resolved_links, links)):
        if link.offset is None:
            rl.offset = auto_offsets.get(i, 0)


def compute_theme_line_y_offsets(
    theme_lines: List[Tuple[str, Optional[int]]],
    positions: Dict[str, Tuple[int, int]],
    spacing: int = 30,
) -> None:
    """Auto-assign Y positions to ThemeLines without explicit y.

    Modifies positions dict in place.

    Args:
        theme_lines: List of (entity_id, explicit_x_or_none) for ThemeLines needing auto-y.
        positions: Dict to update with computed (x, y) positions.
        spacing: Vertical spacing between auto-positioned ThemeLines.
    """
    for idx, (tl_id, tl_x) in enumerate(theme_lines):
        if tl_id not in positions:
            positions[tl_id] = (tl_x if tl_x is not None else 0, idx * spacing)


def apply_grade_defaults(
    items: List[Any],
    grade_params: List[Tuple[str, Optional[int]]],
) -> None:
    """Apply grade default indices to items and their cards.

    Modifies items in place.

    Args:
        items: List of resolved entities or links with grade_one/two/three and cards attrs.
        grade_params: List of (attr_name, default_index) tuples. None index means skip.
    """
    for item in items:
        for attr, default_idx in grade_params:
            if default_idx is None:
                continue
            if getattr(item, attr) is None:
                setattr(item, attr, default_idx)
            for card in (item.cards or []):
                if getattr(card, attr) is None:
                    setattr(card, attr, default_idx)


def resolve_grade_names(
    items: List[Any],
    grade_specs: List[Tuple[str, List[str]]],
) -> None:
    """Resolve string grade names on resolved items (and their cards) to int indices.

    Grade fields on entities/links/cards may be either:
    - ``None`` — left alone
    - an ``int`` (or digit-string) — coerced to ``int``
    - a string name — looked up in the corresponding grade items list

    Validation has already run, so any unknown name encountered here means the
    chart was built without calling ``validate()``; we silently fall back to
    ``None`` so the build still produces XML and downstream defaults can apply.

    Modifies items in place.

    Args:
        items: List of ``ResolvedEntity`` or ``ResolvedLink``.
        grade_specs: List of ``(attr_name, items_list)`` tuples — e.g.
            ``[('grade_one', ['Reliable', 'Unreliable']), ...]``.
    """
    def _resolve_one(val: Any, names: List[str]) -> Optional[int]:
        if val is None:
            return None
        if isinstance(val, bool):
            return None
        if isinstance(val, int):
            return val
        try:
            return int(val)  # digit string
        except (TypeError, ValueError):
            pass
        s = str(val).strip()
        if not s:
            return None
        if names and s in names:
            return names.index(s)
        return None

    for item in items:
        for attr, names in grade_specs:
            setattr(item, attr, _resolve_one(getattr(item, attr), names))
            for card in (item.cards or []):
                setattr(card, attr, _resolve_one(getattr(card, attr), names))


# ── Geo-map transforms ──────────────────────────────────────────────────────


def _norm_geo_key(s: Any, fold_accents: bool) -> str:
    """Canonical form for geo lookup keys and entity attribute values.

    Always lowercases and strips. When ``fold_accents`` is true, also folds
    diacritics via Unicode NFKD so ``São Paulo`` matches ``Sao Paulo``.
    """
    out = str(s).strip().lower()
    if fold_accents:
        out = ''.join(
            c for c in unicodedata.normalize('NFKD', out)
            if not unicodedata.combining(c)
        )
    return out


def resolve_geo_data(
    geo_map: 'GeoMapCfg',
    data_dir: Optional[Path] = None,
) -> Dict[str, Tuple[float, float]]:
    """Merge inline ``data`` and ``data_file`` into a normalised lookup.

    Keys are lowercased and stripped for case-insensitive matching. When
    ``geo_map.accent_insensitive`` is true (the default), diacritics are
    folded as well so ``São Paulo`` matches ``Sao Paulo``.

    Returns:
        Dict mapping normalised key to (latitude, longitude).
    """
    fold = geo_map.accent_insensitive if geo_map.accent_insensitive is not None else True
    merged: Dict[str, Tuple[float, float]] = {}

    # Load external file first (inline data wins on conflict)
    if geo_map.data_file:
        fpath = Path(geo_map.data_file)
        if data_dir and not fpath.is_absolute():
            fpath = data_dir / fpath
        text = fpath.read_text(encoding='utf-8')
        ext = fpath.suffix.lower()
        if ext in ('.yaml', '.yml'):
            try:
                import yaml
            except ImportError:
                raise ImportError(
                    "pyyaml is required for YAML geo_map data_file. "
                    "Install with: pip install anxwritter[yaml]"
                )
            raw = yaml.safe_load(text) or {}
        else:
            raw = json.loads(text)
        for k, v in raw.items():
            merged[_norm_geo_key(k, fold)] = (float(v[0]), float(v[1]))

    # Inline data overrides file data
    if geo_map.data:
        for k, v in geo_map.data.items():
            merged[_norm_geo_key(k, fold)] = (float(v[0]), float(v[1]))

    return merged


def match_geo_entities(
    entities: List[Any],
    geo_data: Dict[str, Tuple[float, float]],
    attribute_name: str,
    accent_insensitive: bool = True,
) -> Dict[str, List[Tuple[str, float, float]]]:
    """Match entities to geo data by attribute value.

    Looks up ``attribute_name`` in each entity's ``attributes`` dict,
    normalises the value (str, lowercase, stripped, optionally NFKD-folded),
    and checks against the geo_data keys. The caller is responsible for
    passing the same ``accent_insensitive`` value used to build ``geo_data``.

    Returns:
        Dict mapping normalised geo key to list of
        ``(entity_id, latitude, longitude)`` tuples.
    """
    # Attribute *name* lookup is always accent- and case-insensitive — the
    # field name is part of the schema, not user data, so folding it is safe.
    attr_norm = _norm_geo_key(attribute_name, fold_accents=True)
    matched: Dict[str, List[Tuple[str, float, float]]] = defaultdict(list)

    for entity in entities:
        attrs = getattr(entity, 'attributes', None) or {}
        val = None
        for k, v in attrs.items():
            if _norm_geo_key(k, fold_accents=True) == attr_norm:
                val = v
                break
        if val is None:
            continue
        norm_val = _norm_geo_key(val, fold_accents=accent_insensitive)
        if norm_val in geo_data:
            lat, lon = geo_data[norm_val]
            eid = getattr(entity, 'id', str(entity))
            matched[norm_val].append((eid, lat, lon))

    return matched


def compute_geo_positions(
    matched: Dict[str, List[Tuple[str, float, float]]],
    positions: Dict[str, Tuple[int, int]],
    width: int = 3000,
    height: int = 2000,
    spread_radius: int = 0,
) -> Tuple[int, int, int, int]:
    """Project matched geo coordinates onto canvas and update positions dict.

    Uses equirectangular projection with auto-fit to ``width x height``.
    Y is inverted (latitude increases north, canvas Y increases down).

    Args:
        matched: Output from ``match_geo_entities``.
        positions: Builder ``_positions`` dict to update in place.
        width: Canvas area width.
        height: Canvas area height.
        spread_radius: Circle radius for same-key entity spread.

    Returns:
        ``(min_x, min_y, max_x, max_y)`` bounding box of all geo-positioned
        entities (including spread), for computing unmatched entity offset.
    """
    # Collect all lat/lon values
    all_points: List[Tuple[str, float, float]] = []
    for entries in matched.values():
        all_points.extend(entries)

    if not all_points:
        return (0, 0, 0, 0)

    lats = [p[1] for p in all_points]
    lons = [p[2] for p in all_points]

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    # Add 10% padding
    lat_range = max_lat - min_lat or 1.0
    lon_range = max_lon - min_lon or 1.0
    pad_lat = lat_range * 0.1
    pad_lon = lon_range * 0.1
    min_lat -= pad_lat
    max_lat += pad_lat
    min_lon -= pad_lon
    max_lon += pad_lon
    lat_range = max_lat - min_lat
    lon_range = max_lon - min_lon

    # Track bounding box of placed entities
    bbox_min_x, bbox_min_y = float('inf'), float('inf')
    bbox_max_x, bbox_max_y = float('-inf'), float('-inf')

    for norm_key, entries in matched.items():
        # All entries for this key share the same lat/lon
        lat, lon = entries[0][1], entries[0][2]
        # Equirectangular projection
        cx = int((lon - min_lon) / lon_range * width)
        cy = int((max_lat - lat) / lat_range * height)  # Y inverted

        n = len(entries)
        for idx, (eid, _lat, _lon) in enumerate(entries):
            # Entities with explicit positions already skip geo — but check anyway
            if eid in positions:
                continue
            if spread_radius > 0 and n > 1:
                angle = 2 * math.pi * idx / n
                ex = cx + int(spread_radius * math.cos(angle))
                ey = cy + int(spread_radius * math.sin(angle))
            else:
                ex, ey = cx, cy
            positions[eid] = (ex, ey)
            bbox_min_x = min(bbox_min_x, ex)
            bbox_min_y = min(bbox_min_y, ey)
            bbox_max_x = max(bbox_max_x, ex)
            bbox_max_y = max(bbox_max_y, ey)

    if bbox_min_x == float('inf'):
        return (0, 0, 0, 0)
    return (int(bbox_min_x), int(bbox_min_y), int(bbox_max_x), int(bbox_max_y))


def inject_geo_attributes(
    resolved_entities: List['ResolvedEntity'],
    matched: Dict[str, List[Tuple[str, float, float]]],
    lat_ref_id: str,
    lon_ref_id: str,
) -> None:
    """Append Latitude/Longitude ResolvedAttr entries to matching entities.

    Modifies resolved entities in place.

    Args:
        resolved_entities: List of ResolvedEntity objects.
        matched: Output from ``match_geo_entities`` — normalised key to
            ``[(entity_id, lat, lon), ...]``.
        lat_ref_id: XML Id for the Latitude AttributeClass.
        lon_ref_id: XML Id for the Longitude AttributeClass.
    """
    from .resolved import ResolvedAttr

    # Build entity_id -> (lat, lon) lookup
    id_to_coords: Dict[str, Tuple[float, float]] = {}
    for entries in matched.values():
        for eid, lat, lon in entries:
            id_to_coords[eid] = (lat, lon)

    for re in resolved_entities:
        if re.identity in id_to_coords:
            lat, lon = id_to_coords[re.identity]
            re.attributes.append(ResolvedAttr('Latitude', lat_ref_id, str(lat)))
            re.attributes.append(ResolvedAttr('Longitude', lon_ref_id, str(lon)))
