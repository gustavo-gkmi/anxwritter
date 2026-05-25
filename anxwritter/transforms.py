"""
Data transformation functions for anxwritter chart building.

These are pure functions that transform resolved entity/link data
without mutating original user objects.
"""
from __future__ import annotations

import bisect
import colorsys
import json
import math
import string
import yaml
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

from .colors import coerce_color, interpolate_ramp, rgb_to_colorref
from .enums import Representation

if TYPE_CHECKING:
    from .resolved import ResolvedEntity, ResolvedLink
    from .models import AttributeClass, Link, GeoMapCfg


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
    for indices in pair_link_indices.values():
        for idx, off in zip(
            indices,
            _compute_symmetric_offsets(len(indices), spacing),
            strict=True,
        ):
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
    for rl, link in zip(resolved_links, links, strict=True):
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
    for i, (rl, link) in enumerate(zip(resolved_links, links, strict=True)):
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


def fold_key(s: Any, *, accents: bool, case: bool) -> str:
    """Canonical comparison key: strip, optional case-fold, optional accent-fold.

    Shared by geo-attribute matching and categorical-style lookup. ``case``
    lowercases; ``accents`` folds diacritics via Unicode NFKD so ``São Paulo``
    matches ``Sao Paulo``.
    """
    out = str(s).strip()
    if case:
        out = out.lower()
    if accents:
        out = ''.join(
            c for c in unicodedata.normalize('NFKD', out)
            if not unicodedata.combining(c)
        )
    return out


def _norm_geo_key(s: Any, fold_accents: bool) -> str:
    """Canonical form for geo lookup keys / entity attribute values
    (always case-folded). See :func:`fold_key`."""
    return fold_key(s, accents=fold_accents, case=True)


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

    for entries in matched.values():
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


# ── Multi-attribute display synthesizers (attribute sibling + label) ─────────

_DT_PARSE_FMTS = (
    '%Y-%m-%dT%H:%M:%S.%f',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%d',
)


def _parse_datetime_value(raw):
    """Parse a stringified datetime/date attribute value back to a datetime
    object so f-string-style format specs like ``{d:%d/%m/%Y}`` work.

    Returns the original string if no known format matches — the caller's
    ``format_map`` will then raise ``ValueError`` and the transform's
    fallback will surface it as a per-item runtime issue rather than a
    silent miss.
    """
    from datetime import datetime as _dt
    if not isinstance(raw, str):
        return raw
    for fmt in _DT_PARSE_FMTS:
        try:
            return _dt.strptime(raw, fmt)
        except ValueError:
            continue
    return raw


class _SeparatorFormatter(string.Formatter):
    """``str.Formatter`` subclass that swaps decimal/thousand separators in
    numeric output.

    Applied per-substitution, not globally on the final string — literal
    commas and periods in the static template (``"qtd: {qty}, total"``) are
    untouched, only the formatted *values* get the swap. Implementation: run
    the standard format step first, detect whether the value is numeric, then
    do a two-step rewrite via a non-conflicting sentinel character.
    """

    def __init__(self, decimal_sep: str = '.', thousand_sep: str = ','):
        super().__init__()
        self._dec = decimal_sep
        self._thou = thousand_sep

    def format_field(self, value, format_spec):
        out = super().format_field(value, format_spec)
        # Skip swap when value isn't numeric — `{qty:>10}` on a string
        # shouldn't have its dots and commas mangled.
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return out
        # Only swap if user picked non-default separators.
        if self._dec == '.' and self._thou == ',':
            return out
        # Two-step swap via sentinel so the same chars don't collide.
        # Python's `,` format spec always uses ',' for thousands and '.' for
        # decimal regardless of locale, which is the contract we rely on.
        SENT = '\x00'
        return (
            out.replace(',', SENT)
               .replace('.', self._dec)
               .replace(SENT, self._thou)
        )


def _ac_type_index(attribute_classes) -> Dict[str, str]:
    """Map AC name → lowercased type string (for datetime source detection)."""
    out: Dict[str, str] = {}
    for ac in attribute_classes:
        if not ac.name:
            continue
        t = getattr(ac, 'type', None)
        if hasattr(t, 'value'):
            t = t.value
        if t is not None:
            out[ac.name] = str(t).lower()
    return out


def _display_kind(disp: Any) -> str:
    return (getattr(disp, 'kind', None) or 'both').lower()


def _item_kind_matches(kind: str, is_link: bool) -> bool:
    """True when a ``kind`` filter ('entity'|'link'|'both') applies to an item."""
    return kind != 'entity' if is_link else kind != 'link'


def _display_source_metas(sources, ac_type_by_name):
    """Cache per-source resolution tuples for one display entry.

    Each tuple: ``(attribute_name, alias_key, missing_policy, placeholder, is_datetime)``.
    """
    metas: List[Tuple[str, str, str, str, bool]] = []
    for src in sources:
        attr_name = getattr(src, 'attribute', None)
        if not attr_name:
            continue
        alias = getattr(src, 'alias', None) or attr_name
        missing = getattr(src, 'missing', None) or 'skip'
        placeholder = getattr(src, 'placeholder', None) or ''
        is_dt = ac_type_by_name.get(attr_name) == 'datetime'
        metas.append((attr_name, alias, missing, placeholder, is_dt))
    return metas


def _render_display(ri, template, source_metas, formatter) -> Optional[str]:
    """Render one item through a template; return ``None`` to skip the item.

    Applies per-source missing policy (``skip``/``error`` → skip the item,
    ``substitute`` → placeholder), parses datetime sources, and coerces
    numeric strings so format specs operate on the numeric value.
    """
    attr_lookup: Dict[str, str] = {ra.class_name: ra.value_str for ra in ri.attributes}
    fmt_dict: Dict[str, Any] = {}
    for attr_name, alias, missing, placeholder, is_dt in source_metas:
        raw = attr_lookup.get(attr_name)
        if raw is None:
            if missing == 'skip' or missing == 'error':
                # 'error' was already surfaced at validate time; defensive skip.
                return None
            fmt_dict[alias] = placeholder  # 'substitute'
            continue
        if is_dt:
            val: Any = _parse_datetime_value(raw)
        else:
            # int first (preserves `:d`), then float, else the raw string.
            try:
                val = int(raw)
            except (TypeError, ValueError):
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    val = raw
        fmt_dict[alias] = val
    try:
        return formatter.vformat(template, (), fmt_dict)
    except (ValueError, KeyError, IndexError, TypeError):
        # Defensive — validate() catches static template syntax errors; this
        # covers runtime corner cases like a value/format-spec type mismatch.
        return None


def expand_display_attributes(
    resolved_entities,
    resolved_links,
    displays,
    attribute_classes,
    builder,
    att_class_config,
):
    """Synthesize text-sibling AttributeClasses from ``display_attribute`` entries.

    Each entry renders its template into a sibling AC named ``attribute_name``.
    Entries are scoped by ``kind`` (entity/link/both) and optional ``type``;
    for a given item and ``attribute_name`` a type-scoped entry wins over an
    untyped one (genuine ties are rejected by validation).

    Source AC visibility is NOT mutated. A visible source AC is allowed: its
    raw value renders alongside the synthesized sibling (a deliberate
    double-render). Only visible *datetime* sources are rejected, by the
    independent ``DATETIME_AC_FORBIDS_VISIBLE`` guard.
    """
    from .resolved import ResolvedAttr

    if not displays:
        return

    ac_type = _ac_type_index(attribute_classes)
    # (kind, type_filter, attr_name, sib_ref_id, template, source_metas, formatter)
    metas: List[tuple] = []
    for disp in displays:
        template = getattr(disp, 'template', None)
        sources = getattr(disp, 'sources', None) or []
        attr_name = getattr(disp, 'attribute_name', None)
        if not template or not sources or not attr_name:
            # Validation already flagged this entry.
            continue

        sib_ref_id = builder._att_class_id(attr_name, 'AttText')
        sibling_row: Dict[str, Any] = {'type': 'text', 'visible': True, 'show_value': True}
        inner = getattr(disp, 'attribute_class', None)
        if inner is not None:
            for fn in ('prefix', 'suffix', 'decimal_places', 'show_value',
                       'show_date', 'show_time', 'show_seconds', 'show_if_set',
                       'show_class_name', 'show_symbol', 'visible',
                       'is_user', 'user_can_add', 'user_can_remove',
                       'icon_file', 'semantic_type',
                       'merge_behaviour', 'paste_behaviour'):
                v = getattr(inner, fn, None)
                if v is not None:
                    sibling_row[fn] = v
            inner_font = getattr(inner, 'font', None)
            if inner_font is not None:
                sibling_row['font'] = inner_font
        att_class_config[attr_name] = sibling_row

        formatter = _SeparatorFormatter(
            getattr(disp, 'decimal_separator', None) or '.',
            getattr(disp, 'thousand_separator', None) or ',',
        )
        metas.append((
            _display_kind(disp), getattr(disp, 'type', None), attr_name,
            sib_ref_id, template, _display_source_metas(sources, ac_type), formatter,
        ))

    def _paint(items, is_link):
        for ri in items:
            item_type = ri.link_type if is_link else ri.entity_type
            # Most-specific applicable entry per attribute_name (typed > untyped).
            best: Dict[str, Tuple[int, tuple]] = {}
            for kind, tfilter, attr_name, sib_ref_id, template, smetas, fmt in metas:
                if not _item_kind_matches(kind, is_link):
                    continue
                if tfilter is not None and tfilter != item_type:
                    continue
                spec = 1 if tfilter is not None else 0
                cur = best.get(attr_name)
                if cur is None or spec > cur[0]:
                    best[attr_name] = (spec, (attr_name, sib_ref_id, template, smetas, fmt))
            for _attr_name, (_spec, (an, sib_ref_id, template, smetas, fmt)) in best.items():
                rendered = _render_display(ri, template, smetas, fmt)
                if rendered is not None:
                    ri.attributes.append(ResolvedAttr(an, sib_ref_id, rendered))

    _paint(resolved_entities, False)
    _paint(resolved_links, True)


def expand_display_labels(
    resolved_entities,
    resolved_links,
    displays,
    attribute_classes,
):
    """Render ``display_label`` entries into entity/link labels.

    Entries are scoped by ``kind`` / ``type``; for a given item the
    most-specific applicable entry wins (type-scoped over untyped; genuine
    ties are rejected by validation). ``override_existing`` controls whether a
    pre-existing label is replaced (default keeps the explicit label).
    """
    if not displays:
        return

    ac_type = _ac_type_index(attribute_classes)
    # (kind, type_filter, template, source_metas, formatter, override_existing)
    metas: List[tuple] = []
    for disp in displays:
        template = getattr(disp, 'template', None)
        sources = getattr(disp, 'sources', None) or []
        if not template or not sources:
            # Validation already flagged this entry.
            continue
        formatter = _SeparatorFormatter(
            getattr(disp, 'decimal_separator', None) or '.',
            getattr(disp, 'thousand_separator', None) or ',',
        )
        metas.append((
            _display_kind(disp), getattr(disp, 'type', None), template,
            _display_source_metas(sources, ac_type), formatter,
            bool(getattr(disp, 'override_existing', False)),
        ))

    def _paint(items, is_link):
        for ri in items:
            item_type = ri.link_type if is_link else ri.entity_type
            best = None  # (spec, template, source_metas, formatter, override)
            for kind, tfilter, template, smetas, fmt, override in metas:
                if not _item_kind_matches(kind, is_link):
                    continue
                if tfilter is not None and tfilter != item_type:
                    continue
                spec = 1 if tfilter is not None else 0
                if best is None or spec > best[0]:
                    best = (spec, template, smetas, fmt, override)
            if best is None:
                continue
            _spec, template, smetas, fmt, override = best
            # A resolved entity label defaults to its identity (id) and a link
            # label defaults to ''. Treat either as "not explicitly set" so a
            # display_label fills it; a genuinely user-set label is preserved
            # unless override_existing.
            identity = getattr(ri, 'identity', None)
            explicit = bool(ri.label) and ri.label != identity
            if explicit and not override:
                continue
            rendered = _render_display(ri, template, smetas, fmt)
            if rendered is not None:
                ri.label = rendered

    _paint(resolved_entities, False)
    _paint(resolved_links, True)


# ── Link styling: scales, intensity, categorical ────────────────────────────


def _percentile(sorted_vals: List[float], q: float) -> float:
    """Linear-interpolation percentile (``q`` in 0–100).

    Used for the ``'robust'`` domain mode (5/95 percentile) so a single
    outlier doesn't compress the rest of the data into the bottom decile.
    """
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_vals[0]
    pos = (q / 100.0) * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def resolve_intensity_domain(
    values: List[float],
    explicit_domain: Any,
) -> Tuple[float, float]:
    """Resolve a domain spec to a concrete ``(lo, hi)`` pair.

    - ``None`` → data ``min`` / ``max``.
    - ``'robust'`` → 5th / 95th percentile; falls back to data range if those
      collapse (e.g. < 5 % of points were unique).
    - ``[a, b]`` → exact pair.

    The caller is responsible for ensuring ``values`` is non-empty when the
    chosen scale requires it; this helper returns ``(0.0, 1.0)`` for empty
    input so the rest of the pipeline can no-op cleanly.
    """
    if not values:
        return (0.0, 1.0)
    if isinstance(explicit_domain, str) and explicit_domain == 'robust':
        s = sorted(values)
        lo = _percentile(s, 5.0)
        hi = _percentile(s, 95.0)
        if lo == hi:
            lo, hi = min(values), max(values)
        return lo, hi
    if isinstance(explicit_domain, (list, tuple)) and len(explicit_domain) == 2:
        return float(explicit_domain[0]), float(explicit_domain[1])
    return min(values), max(values)


def _diverging_t(
    v: float,
    lo: float,
    mid: float,
    hi: float,
    clip: bool,
) -> float:
    """Map ``v`` to ``t`` in [0, 1] with ``mid`` pinned at 0.5.

    Used when ``intensity.color.diverging=True``. Linear within each half;
    other scales are ignored when diverging is on — sentiment-style ramps
    benefit from a symmetric linear split, and supporting log/sqrt on each
    half independently is reserved for a future release.
    """
    if clip:
        if v < lo:
            v = lo
        if v > hi:
            v = hi
    if v <= mid:
        if mid <= lo:
            return 0.0
        return max(0.0, min(0.5, 0.5 * (v - lo) / (mid - lo)))
    if hi <= mid:
        return 1.0
    return max(0.5, min(1.0, 0.5 + 0.5 * (v - mid) / (hi - mid)))


def apply_scale(
    v: float,
    lo: float,
    hi: float,
    scale: str,
    power: float = 0.5,
    clip: bool = True,
    sorted_vals: Optional[Sequence[float]] = None,
) -> float:
    """Map a single value to ``t`` ∈ [0, 1] via the requested scale.

    Returns ``0.5`` for degenerate domains (``lo >= hi``). Final ``t`` is
    always clamped to ``[0, 1]`` regardless of ``clip`` — ``clip`` only
    controls whether ``v`` is clamped to ``[lo, hi]`` before scaling.

    ``sorted_vals`` is only consulted for ``scale='quantile'`` (must contain
    the precomputed sorted attribute values across all matched links).
    """
    if clip:
        if v < lo:
            v = lo
        if v > hi:
            v = hi
    if hi <= lo:
        return 0.5
    if scale == 'linear':
        t = (v - lo) / (hi - lo)
    elif scale == 'log':
        # Validation guarantees lo > 0 and v > 0 when this path is reachable.
        if v <= 0 or lo <= 0:
            t = 0.0
        else:
            t = (math.log(v) - math.log(lo)) / (math.log(hi) - math.log(lo))
    elif scale == 'sqrt':
        t = ((max(v, lo) - lo) ** 0.5) / ((hi - lo) ** 0.5)
    elif scale == 'power':
        t = ((max(v, lo) - lo) / (hi - lo)) ** power
    elif scale == 'quantile':
        if not sorted_vals or len(sorted_vals) <= 1:
            t = 0.5
        else:
            lo_rank = bisect.bisect_left(sorted_vals, v)
            hi_rank = bisect.bisect_right(sorted_vals, v) - 1
            if hi_rank < 0:
                t = 0.0
            else:
                avg_rank = (lo_rank + hi_rank) / 2.0
                t = avg_rank / (len(sorted_vals) - 1)
    else:
        t = 0.0
    return max(0.0, min(1.0, t))


def _normalize_categorical_key(s: Any, fold_accents: bool, fold_case: bool) -> str:
    """Canonical form for categorical-style lookup keys. See :func:`fold_key`."""
    return fold_key(s, accents=fold_accents, case=fold_case)


def _resolve_color_to_int(c: Any) -> Optional[int]:
    """Convert a color spec to a COLORREF int, or return None on failure.

    Used by the intensity / categorical transforms when reading user-supplied
    color values (ramp entries, categorical line_color). Validation has already
    rejected unresolvable colors, so this should never silently return None for
    valid input — the fallback only kicks in if someone bypasses validate().
    """
    try:
        return coerce_color(c)
    except (ValueError, TypeError):
        return None


def _intensity_collect_values(
    links: List['Link'],
    attr_name: str,
) -> Tuple[Dict[int, float], List[float]]:
    """Collect (link_index → value) and a sorted-values list for one attribute.

    Returns ``(by_index, sorted_vals)``. ``by_index`` keys correspond to
    indices in ``links``; entries with missing / non-numeric values are absent.
    ``sorted_vals`` is the sorted list of present values, used by the quantile
    scale and robust-domain math.
    """
    by_index: Dict[int, float] = {}
    for i, link in enumerate(links):
        attrs = getattr(link, 'attributes', None) or {}
        if attr_name not in attrs:
            continue
        v = attrs[attr_name]
        if v is None or isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            if isinstance(v, float) and math.isnan(v):
                continue
            by_index[i] = float(v)
    sorted_vals = sorted(by_index.values())
    return by_index, sorted_vals


def _resolve_intensity_sub(
    icfg: Any,
    sub_name: str,
) -> Optional[Dict[str, Any]]:
    """Flatten an IntensityCfg width or color sub-block into a plain dict.

    Inherits attribute/scale/domain/clip/power from the parent ``IntensityCfg``
    when the sub-block leaves them unset. Returns ``None`` when the sub-block
    is absent (so the caller can skip cleanly).
    """
    sub = getattr(icfg, sub_name, None)
    if sub is None:
        return None
    return {
        'attribute': getattr(sub, 'attribute', None) or getattr(icfg, 'attribute', None),
        'scale': getattr(sub, 'scale', None) or getattr(icfg, 'scale', None) or 'sqrt',
        'domain': (getattr(sub, 'domain', None) if getattr(sub, 'domain', None) is not None
                   else getattr(icfg, 'domain', None)),
        'clip': getattr(sub, 'clip', None) if getattr(sub, 'clip', None) is not None else
                (getattr(icfg, 'clip', None) if getattr(icfg, 'clip', None) is not None else True),
        'power': getattr(sub, 'power', None) if getattr(sub, 'power', None) is not None else 0.5,
        'range': getattr(sub, 'range', None),
        'ramp': getattr(sub, 'ramp', None),
        'space': getattr(sub, 'space', None) or 'rgb_linear',
        'diverging': bool(getattr(sub, 'diverging', None)),
        'midpoint': getattr(sub, 'midpoint', None),
    }


def apply_link_intensity(
    resolved_links: List['ResolvedLink'],
    links: List['Link'],
    icfg: Any,
) -> None:
    """Apply numeric-attribute → width/color styling to resolved links.

    Modifies ``resolved_links`` in place. Only writes ``line_width`` /
    ``line_color`` when the corresponding original ``Link`` field is unset
    (None) — preserves the precedence rule that explicit per-link values win.

    Assumes validation has passed: any bad attribute/scale/range combinations
    are surfaced by ``validate_styling`` at ``validate()`` time, not here.
    No-ops when ``icfg`` is ``None`` or when neither ``width`` nor ``color``
    is configured.
    """
    if icfg is None:
        return

    width_cfg = _resolve_intensity_sub(icfg, 'width')
    color_cfg = _resolve_intensity_sub(icfg, 'color')
    if width_cfg is None and color_cfg is None:
        return

    def _apply_one(cfg: Dict[str, Any], target: str) -> None:
        attr_name = cfg['attribute']
        if not attr_name:
            return
        by_index, sorted_vals = _intensity_collect_values(links, attr_name)
        if not by_index:
            return

        # Resolve domain
        lo, hi = resolve_intensity_domain(list(by_index.values()), cfg['domain'])

        # Pre-resolve ramp colors to COLORREF ints
        ramp_ints: Optional[List[int]] = None
        if target == 'color':
            ramp = cfg.get('ramp') or []
            ramp_ints = []
            for c in ramp:
                ci = _resolve_color_to_int(c)
                if ci is not None:
                    ramp_ints.append(ci)
            if len(ramp_ints) < 2:
                return  # validation should have caught this; bail safely

        # Contract: ``links`` is the filtered list aligned 1:1 with
        # ``resolved_links`` (same convention as ``apply_link_entity_colors``).
        for rl, link in zip(resolved_links, links, strict=True):
            attrs = getattr(link, 'attributes', None) or {}
            v = attrs.get(attr_name)
            if v is None or isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            if isinstance(v, float) and math.isnan(v):
                continue
            v = float(v)

            # Compute t
            if target == 'color' and cfg.get('diverging') and cfg.get('midpoint') is not None:
                t = _diverging_t(v, lo, float(cfg['midpoint']), hi, cfg['clip'])
            else:
                t = apply_scale(
                    v, lo, hi,
                    scale=cfg['scale'],
                    power=cfg['power'],
                    clip=cfg['clip'],
                    sorted_vals=sorted_vals if cfg['scale'] == 'quantile' else None,
                )

            # Project to output
            if target == 'width':
                if link.line_width is not None:
                    continue  # explicit user value wins
                rng = cfg['range']
                w = rng[0] + (rng[1] - rng[0]) * t
                rl.line_width = max(0, int(round(w)))
            else:  # color
                if link.line_color is not None:
                    continue
                assert ramp_ints is not None
                rl.line_color = interpolate_ramp(ramp_ints, t, cfg['space'])

    if width_cfg is not None:
        _apply_one(width_cfg, 'width')
    if color_cfg is not None:
        _apply_one(color_cfg, 'color')


def apply_link_categorical(
    resolved_links: List['ResolvedLink'],
    links: List['Link'],
    ccfg: Any,
) -> None:
    """Apply categorical attribute → style lookup to resolved links.

    Modifies ``resolved_links`` in place. Same precedence rule as
    ``apply_link_intensity``: only writes where the original ``Link`` field
    was unset, so user-explicit values always win.

    Resolution per link:
      1. Read ``link.attributes[attribute_name]``. If absent, apply the
         ``missing`` policy (``fallback`` and ``skip`` both leave the link
         alone; ``error`` was already surfaced by ``validate_styling``).
      2. Normalise the value per ``case_sensitive`` / ``accent_insensitive``
         flags. ``styles`` keys are normalised the same way at first use.
      3. Look up in ``styles``; fall through to ``default`` if no match.
      4. Apply ``line_color`` / ``line_width`` / ``strength`` from the style.
    """
    if ccfg is None:
        return
    attr_name = getattr(ccfg, 'attribute', None)
    styles = getattr(ccfg, 'styles', None) or {}
    if not attr_name or not styles:
        return

    case_sensitive = bool(getattr(ccfg, 'case_sensitive', None) or False)
    accent_insensitive = getattr(ccfg, 'accent_insensitive', None)
    fold_accents = True if accent_insensitive is None else bool(accent_insensitive)
    fold_case = not case_sensitive

    # Normalise styles keys once.
    norm_styles: Dict[str, Any] = {}
    for k, st in styles.items():
        norm_styles[_normalize_categorical_key(k, fold_accents, fold_case)] = st
    default_style = getattr(ccfg, 'default', None)

    for rl, link in zip(resolved_links, links, strict=True):
        attrs = getattr(link, 'attributes', None) or {}
        raw_val = attrs.get(attr_name)
        if raw_val is None:
            chosen = default_style if default_style is not None else None
        else:
            key = _normalize_categorical_key(raw_val, fold_accents, fold_case)
            chosen = norm_styles.get(key, default_style)
        if chosen is None:
            continue

        lc = getattr(chosen, 'line_color', None)
        lw = getattr(chosen, 'line_width', None)
        strn = getattr(chosen, 'strength', None)

        if lc is not None and link.line_color is None:
            resolved = _resolve_color_to_int(lc)
            if resolved is not None:
                rl.line_color = resolved
        if lw is not None and link.line_width is None:
            try:
                rl.line_width = max(0, int(lw))
            except (TypeError, ValueError):
                pass
        if strn is not None and link.strength is None:
            rl.strength = str(strn)


def generate_styling_legend(
    styling: Any,
    links: List['Link'],
    attribute_classes: Optional[List['AttributeClass']] = None,
) -> List[Dict[str, Any]]:
    """Build legend dicts for any styling block that opted in via ``legend: true``.

    Returns a list of ``LegendItem``-shaped dicts ready to append to the chart's
    legend item list. Intensity legends emit ``legend_count`` rows (default 5)
    sampled in scale-space so the steps are uniform along the curve, not the
    data axis. Categorical legends emit one row per ``styles`` entry in
    insertion order.

    No-ops when ``styling`` or ``styling.links`` is ``None``, or when neither
    sub-block sets ``legend: true``.
    """
    out: List[Dict[str, Any]] = []
    if styling is None or getattr(styling, 'links', None) is None:
        return out

    icfg = getattr(styling.links, 'intensity', None)
    ccfg = getattr(styling.links, 'categorical', None)

    if icfg is not None and getattr(icfg, 'legend', None):
        out.extend(_intensity_legend_rows(icfg, links, attribute_classes or []))
    if ccfg is not None and getattr(ccfg, 'legend', None):
        out.extend(_categorical_legend_rows(ccfg))

    return out


def _format_legend_value(
    v: float,
    formatter: '_SeparatorFormatter',
    *,
    prefix: str = '',
    suffix: str = '',
    decimal_places: Optional[int] = None,
) -> str:
    """Format a legend row name using the driving attribute's declared format.

    Mirrors how the value renders in the chart body: the driving
    ``AttributeClass``'s ``prefix`` / ``suffix`` / ``decimal_places``, plus the
    intensity block's declared ``decimal_separator`` / ``thousand_separator``
    (applied via ``formatter``, a shared ``_SeparatorFormatter``). Thousands
    are always grouped — never scientific notation, even for large values.

    When ``decimal_places`` is ``None`` (no declared AC), integers render
    without a fractional part and non-integers fall back to two places.
    """
    if decimal_places is not None:
        body = formatter.format_field(float(v), f",.{int(decimal_places)}f")
    elif float(v) == int(v):
        body = formatter.format_field(int(v), ",")
    else:
        body = formatter.format_field(float(v), ",.2f")
    return f"{prefix}{body}{suffix}"


def _intensity_legend_rows(
    icfg: Any,
    links: List['Link'],
    attribute_classes: Optional[List['AttributeClass']] = None,
) -> List[Dict[str, Any]]:
    """Produce N sample rows along the intensity scale.

    Samples are picked uniformly in ``t``-space (the normalised [0, 1] axis),
    so a log scale shows a geometric progression of values. The corresponding
    width / color is computed via the same machinery the transform uses. Row
    labels reuse the driving attribute's declared ``AttributeClass`` format
    (``prefix`` / ``suffix`` / ``decimal_places``) and the block's
    ``decimal_separator`` / ``thousand_separator``.
    """
    n = getattr(icfg, 'legend_count', None) or 5
    if n < 2:
        n = 2

    width_cfg = _resolve_intensity_sub(icfg, 'width')
    color_cfg = _resolve_intensity_sub(icfg, 'color')

    # Determine the driving attribute (prefer width's, then color's, then top-level).
    drv_attr = None
    for c in (width_cfg, color_cfg):
        if c is not None and c['attribute']:
            drv_attr = c['attribute']
            break
    if drv_attr is None:
        return []
    by_index, sorted_vals = _intensity_collect_values(links, drv_attr)
    if not by_index:
        return []

    # Label formatting borrows the driving attribute's declared AC format and
    # the block's declared separators (default '.'/',' — Python's native
    # grouping). Suppresses scientific notation on large values.
    src_ac = None
    for ac in (attribute_classes or []):
        if getattr(ac, 'name', None) == drv_attr:
            src_ac = ac
            break
    lbl_prefix = (getattr(src_ac, 'prefix', None) or '') if src_ac else ''
    lbl_suffix = (getattr(src_ac, 'suffix', None) or '') if src_ac else ''
    lbl_dp = getattr(src_ac, 'decimal_places', None) if src_ac else None
    fmt = _SeparatorFormatter(
        getattr(icfg, 'decimal_separator', None) or '.',
        getattr(icfg, 'thousand_separator', None) or ',',
    )

    drv_cfg = width_cfg or color_cfg
    lo, hi = resolve_intensity_domain(list(by_index.values()), drv_cfg['domain'])

    ramp_ints: Optional[List[int]] = None
    if color_cfg is not None:
        ramp_ints = []
        for c in (color_cfg.get('ramp') or []):
            ci = _resolve_color_to_int(c)
            if ci is not None:
                ramp_ints.append(ci)
        if len(ramp_ints) < 2:
            ramp_ints = None

    # Sample t values evenly in [0, 1].
    rows: List[Dict[str, Any]] = []
    for i in range(n):
        t = 0.0 if n == 1 else i / (n - 1)
        # Reverse the scale to recover a representative value for the label.
        v = _invert_scale_t(t, lo, hi, drv_cfg['scale'], drv_cfg['power'], sorted_vals)

        row: Dict[str, Any] = {
            'name': _format_legend_value(
                v, fmt, prefix=lbl_prefix, suffix=lbl_suffix, decimal_places=lbl_dp,
            ),
            'item_type': 'Line',
        }
        if width_cfg is not None:
            rng = width_cfg['range']
            w = rng[0] + (rng[1] - rng[0]) * t
            row['line_width'] = max(0, int(round(w)))
        else:
            row['line_width'] = 1
        if color_cfg is not None and ramp_ints is not None:
            if color_cfg.get('diverging') and color_cfg.get('midpoint') is not None:
                t_color = _diverging_t(v, lo, float(color_cfg['midpoint']), hi, color_cfg['clip'])
            else:
                t_color = t
            row['color'] = interpolate_ramp(ramp_ints, t_color, color_cfg['space'])
        else:
            row['color'] = 0
        rows.append(row)
    return rows


def _invert_scale_t(
    t: float,
    lo: float,
    hi: float,
    scale: str,
    power: float,
    sorted_vals: Sequence[float],
) -> float:
    """Recover a representative value for ``t`` ∈ [0, 1] (legend labelling only).

    For quantile scale this returns the value at rank ``t * (N-1)``; for log/
    sqrt/power it inverts the scale function analytically. Linear is the
    obvious case.
    """
    if hi <= lo:
        return lo
    if scale == 'linear':
        return lo + (hi - lo) * t
    if scale == 'log':
        if lo <= 0:
            return lo + (hi - lo) * t
        return math.exp(math.log(lo) + (math.log(hi) - math.log(lo)) * t)
    if scale == 'sqrt':
        return lo + (hi - lo) * (t ** 2)
    if scale == 'power':
        if power <= 0:
            return lo + (hi - lo) * t
        return lo + (hi - lo) * (t ** (1.0 / power))
    if scale == 'quantile':
        if not sorted_vals:
            return lo + (hi - lo) * t
        idx = int(round(t * (len(sorted_vals) - 1)))
        idx = max(0, min(len(sorted_vals) - 1, idx))
        return sorted_vals[idx]
    return lo + (hi - lo) * t


def _categorical_legend_rows(ccfg: Any) -> List[Dict[str, Any]]:
    """Produce one legend row per ``styles`` entry, in insertion order."""
    rows: List[Dict[str, Any]] = []
    styles = getattr(ccfg, 'styles', None) or {}
    for key, style in styles.items():
        row: Dict[str, Any] = {'name': str(key), 'item_type': 'Line'}
        lc = getattr(style, 'line_color', None)
        lw = getattr(style, 'line_width', None)
        if lc is not None:
            ci = _resolve_color_to_int(lc)
            row['color'] = ci if ci is not None else 0
        else:
            row['color'] = 0
        if lw is not None:
            try:
                row['line_width'] = max(0, int(lw))
            except (TypeError, ValueError):
                row['line_width'] = 1
        else:
            row['line_width'] = 1
        rows.append(row)
    return rows
