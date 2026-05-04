"""
Builds an i2 Analyst's Notebook Exchange (ANX) XML document from typed
entity/link objects.

Embeds all chart data directly in the ANX XML — no separate CSV is required.
The resulting .anx file can be opened in i2 ANB 9+ via File > Open.
"""
from __future__ import annotations

import math
import time as _time
import xml.etree.ElementTree as ET
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

# Register LCX namespace for _fast_serialize tag resolution
ET.register_namespace('lcx', 'http://www.i2group.com/Schemas/2001-12-07/LCXSchema')

from .colors import color_to_colorref
from .enums import Representation, AttributeType
from .models import Link  # for type hints in add_link
from .timing import PhaseTimer
from .utils import _enum_val


# ── Internal attribute tuple ─────────────────────────────────────────────────

class _AttrTuple(NamedTuple):
    class_name: str
    value: Any
    attr_type: AttributeType


# ── <Chart> attribute mapping ────────────────────────────────────────────────
# Ordered list of (settings_path, xml_attr, type_tag) used to build the <Chart> element.
# settings_path is a dotted path on the Settings dataclass (e.g. 'chart.bg_color').
# type_tag: 'bool' → 'true'/'false', 'int'/'float'/'color' → str(), 'str' → pass through.
_CHART_ATTR_MAP: List[Tuple[str, str, str]] = [
    ('chart.bg_color',                          'BackColour',                        'color'),
    ('links_cfg.blank_labels',                  'BlankLinkLabels',                   'bool'),
    ('time.default_date',                       'DefaultDate',                       'str'),
    ('time.default_datetime',                   'DefaultDateTimeForNewChart',        'str'),
    ('time.tick_rate',                          'DefaultTickRate',                   'float'),
    ('links_cfg.spacing',                       'DefaultLinkSpacing',                'float'),
    ('links_cfg.use_default_spacing_when_dragging', 'UseDefaultLinkSpacingWhenDragging', 'bool'),
    ('grid.height',                             'GridHeightSize',                    'float'),
    ('grid.visible',                            'GridVisibleOnAllViews',             'bool'),
    ('grid.width',                              'GridWidthSize',                     'float'),
    ('time.hide_matching_tz_format',            'HideMatchingTimeZoneFormat',        'bool'),
    ('view.hidden_items',                       'HiddenItemsVisibility',             'str'),
    ('chart.bg_filled',                         'IsBackColourFilled',                'bool'),
    ('view.show_all',                           'ShowAllFlag',                       'bool'),
    ('view.show_pages_boundaries',              'ShowPages',                         'bool'),
    ('grid.snap',                               'SnapToGrid',                        'bool'),
    ('chart.rigorous',                          'Rigorous',                          'bool'),
    ('chart.id_reference_linking',              'IdReferenceLinking',                'bool'),
    ('chart.label_merge_rule',                  'LabelRule',                         'str'),
    ('links_cfg.sum_numeric_labels',            'LabelSumNumericLinks',              'bool'),
    ('chart.icon_quality',                      'TypeIconDrawingMode',               'str'),
    ('time.local_tz',                           'UseLocalTimeZone',                  'bool'),
    ('wiring.use_height_for_theme_icon',        'UseWiringHeightForThemeIcon',       'bool'),
    ('wiring.distance_far',                     'WiringDistanceFar',                 'float'),
    ('wiring.distance_near',                    'WiringDistanceNear',                'float'),
    ('wiring.height',                           'WiringHeight',                      'float'),
    ('wiring.spacing',                          'WiringSpacing',                     'float'),
    ('view.cover_sheet_on_open',                'CoverSheetShowOnOpen',              'bool'),
    ('view.time_bar',                           'TimeBarVisible',                    'bool'),
]


# ── Enum short-name → full ANB XML string maps ─────────────────────────────
# _resolve_enum() looks up short lowercase aliases and symbol aliases,
# falling back to passthrough for full ANB names.

def _resolve_enum(value: Any, mapping: Dict[str, str]) -> str:
    """Resolve a short/symbol enum alias to its full ANB XML string."""
    s = _enum_val(value)
    return mapping.get(s.lower(), s) if s else ''

_ARROW_MAP: Dict[str, str] = {
    'head': 'ArrowOnHead', '->': 'ArrowOnHead',
    'tail': 'ArrowOnTail', '<-': 'ArrowOnTail',
    'both': 'ArrowOnBoth', '<->': 'ArrowOnBoth',
}
_DOT_MAP: Dict[str, str] = {
    'solid': 'DotStyleSolid', '-': 'DotStyleSolid',
    'dashed': 'DotStyleDashed', '---': 'DotStyleDashed',
    'dash_dot': 'DotStyleDashDot', '-.': 'DotStyleDashDot',
    'dash_dot_dot': 'DotStyleDashDotDot', '-..': 'DotStyleDashDotDot',
    'dotted': 'DotStyleDotted', '...': 'DotStyleDotted',
}
_ENLARGE_MAP: Dict[str, str] = {
    'half': 'ICEnlargeHalf', 'single': 'ICEnlargeSingle',
    'double': 'ICEnlargeDouble', 'triple': 'ICEnlargeTriple',
    'quadruple': 'ICEnlargeQuadruple',
}
_MULT_MAP: Dict[str, str] = {
    'multiple': 'MultiplicityMultiple',
    'single': 'MultiplicitySingle',
    'directed': 'MultiplicityDirected',
}
_THEME_WIRING_MAP: Dict[str, str] = {
    'keep_event': 'KeepsAtEventHeight',
    'return_theme': 'ReturnsToThemeHeight',
    'next_event': 'GoesToNextEventHeight',
    'no_diversion': 'NoDiversion',
}
_MERGE_MAP: Dict[str, str] = {
    'assign': 'AttMergeAssign', 'noop': 'AttMergeNoOp',
    'add': 'AttMergeAdd', 'add_space': 'AttMergeAddWithSpace',
    'add_line_break': 'AttMergeAddWithLineBreak',
    'max': 'AttMergeMax', 'min': 'AttMergeMin',
    'subtract': 'AttMergeSubtract', 'subtract_swap': 'AttMergeSubtractSwap',
    'or': 'AttMergeOR', 'and': 'AttMergeAND', 'xor': 'AttMergeXOR',
}
# Extend with lowercase canonical forms so passthrough of ANB-prefixed names
# (e.g. 'AttMergeXOR' from legacy configs) canonicalizes correctly via _resolve_enum.
_MERGE_MAP.update({v.lower(): v for v in list(_MERGE_MAP.values())})
_LABEL_RULE_MAP: Dict[str, str] = {
    'merge': 'LabelRuleMerge', 'append': 'LabelRuleAppend',
    'discard': 'LabelRuleDiscard',
}
_HIDDEN_ITEMS_MAP: Dict[str, str] = {
    'hidden': 'ItemsVisibilityHidden', 'normal': 'ItemsVisibilityNormal',
    'grayed': 'ItemsVisibilityGrayed',
}
_LEGEND_ARRANGE_MAP: Dict[str, str] = {
    'wide': 'LegendArrangementWide', 'tall': 'LegendArrangementTall',
    'square': 'LegendArrangementSquare',
}
_LEGEND_ALIGN_MAP: Dict[str, str] = {
    'free': 'LegendAlignmentFree', 'top': 'LegendAlignmentTop',
    'bottom': 'LegendAlignmentBottom', 'left': 'LegendAlignmentLeft',
    'right': 'LegendAlignmentRight',
}
_TEXT_ALIGN_MAP: Dict[str, str] = {
    'centre': 'TextAlignCentre', 'center': 'TextAlignCentre',
    'left': 'TextAlignLeft', 'right': 'TextAlignRight',
}

# Per-field enum maps for _CHART_ATTR_MAP str-type entries
_SETTINGS_ENUM_MAPS: Dict[str, Dict[str, str]] = {
    'chart.label_merge_rule': _LABEL_RULE_MAP,
    'view.hidden_items': _HIDDEN_ITEMS_MAP,
}


def _resolve_path(settings: Any, path: str) -> Any:
    """Walk a dotted path on the Settings dataclass.

    Returns the value at that path, or ``None`` if any segment is missing
    or evaluates to None.
    """
    obj = settings
    for part in path.split('.'):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    return obj


def _fmt_chart_attr(v: Any, t: str) -> str:
    """Serialize a chart config value to its XML attribute string."""
    if t == 'bool':
        return 'true' if v else 'false'
    if t == 'color':
        # Accept named color string, '#RRGGBB', or COLORREF int
        if isinstance(v, int):
            return str(v)
        return str(color_to_colorref(v))
    # YAML's safe_load produces datetime / date objects for unquoted ISO
    # literals.  Python's str(datetime) uses a space separator; ANB needs
    # an ISO 'T' separator for date-typed chart attributes (e.g. DefaultDate,
    # DefaultDateTimeForNewChart).  Format explicitly so quoted-string and
    # unquoted-datetime YAML inputs produce identical XML.
    from datetime import datetime as _dt, date as _date
    if isinstance(v, _dt):
        return v.strftime('%Y-%m-%dT%H:%M:%S')
    if isinstance(v, _date):
        return v.strftime('%Y-%m-%d')
    return str(v)


# ── Attribute type name mapping  ─────────────────────────────────────────────
_ATT_TYPE: Dict[str, str] = {
    AttributeType.TEXT.value:     'AttText',
    AttributeType.NUMBER.value:   'AttNumber',
    AttributeType.DATETIME.value: 'AttTime',   # AttDateTime is invalid; AttTime is the correct ANX type
    AttributeType.FLAG.value:     'AttFlag',
}

# ── Representation → PreferredRepresentation string ─────────────────────────
_PREFERRED_REP: Dict[str, str] = {
    Representation.ICON.value:        'RepresentAsIcon',
    Representation.BOX.value:         'RepresentAsBox',
    Representation.CIRCLE.value:      'RepresentAsCircle',
    # ANB schema only accepts Icon/Box/Circle for PreferredRepresentation in EntityType.
    # ThemeLine, EventFrame and TextBlock entities use the correct visual element inside
    # <Entity> (<Theme>, <Event>, <TextBlock>) — the EntityType declaration falls
    # back to RepresentAsIcon to pass schema validation.
    Representation.EVENT_FRAME.value: 'RepresentAsIcon',
    Representation.THEME_LINE.value:  'RepresentAsIcon',
    Representation.TEXT_BLOCK.value:  'RepresentAsTextBlock',
    # Label maps to RepresentAsBorder per the XSD PreferredRepresentationEnum.
    # XML structure inside <Entity> is under investigation — using <Border><BorderStyle>.
    Representation.LABEL.value:       'RepresentAsBorder',
    # OLE not yet implemented — falls back to Icon.
    Representation.OLE_OBJECT.value:  'RepresentAsOLE',
}

# ── Default Font attribute sets ──────────────────────────────────────────────
_FONT_DEFAULTS_CHART: Dict[str, str] = {
    'BackColour': '16777215', 'Bold': 'false', 'CharSet': 'CharSetDefault',
    'FaceName': 'Tahoma', 'FontColour': '0', 'Italic': 'false',
    'PointSize': '10', 'Strikeout': 'false', 'Underline': 'false',
}
_FONT_DEFAULTS_AC: Dict[str, str] = {
    **_FONT_DEFAULTS_CHART, 'PointSize': '8',
}

def _parse_attrs(attributes: dict) -> List[Tuple[str, str, str]]:
    """Convert an entity/link attributes dict to (name, value_str, type_str) tuples.

    The returned ``type_str`` matches ``AttributeType`` enum values (lowercase),
    so it is a valid key into ``_ATT_TYPE``.

    Type inference:
        bool          → 'flag'     (must check before int since bool is subclass of int)
        int/float     → 'number'
        datetime/date → 'datetime' (date is widened to a midnight datetime)
        str/other     → 'text'
    """
    from datetime import datetime as _dt, date as _date
    result = []
    for name, value in (attributes or {}).items():
        if value is None:
            continue
        if isinstance(value, bool):
            result.append((name, str(value).lower(), AttributeType.FLAG.value))
        elif isinstance(value, _dt):
            result.append((name, value.strftime('%Y-%m-%dT%H:%M:%S'), AttributeType.DATETIME.value))
        elif isinstance(value, _date):
            # YAML's safe_load returns date for unquoted YYYY-MM-DD literals;
            # widen to midnight datetime so the attribute round-trips as AttTime.
            result.append((name, _dt(value.year, value.month, value.day).strftime('%Y-%m-%dT%H:%M:%S'),
                           AttributeType.DATETIME.value))
        elif isinstance(value, (int, float)):
            result.append((name, str(value), AttributeType.NUMBER.value))
        else:
            result.append((name, str(value), AttributeType.TEXT.value))
    return result


def _entity_rep(entity) -> 'Representation':
    """Map entity class type to Representation enum."""
    from .entities import Icon, Box, Circle, ThemeLine, EventFrame, TextBlock, Label
    type_map = {
        Icon: Representation.ICON,
        Box: Representation.BOX,
        Circle: Representation.CIRCLE,
        ThemeLine: Representation.THEME_LINE,
        EventFrame: Representation.EVENT_FRAME,
        TextBlock: Representation.TEXT_BLOCK,
        Label: Representation.LABEL,
    }
    return type_map.get(type(entity), Representation.ICON)


def _entity_style(entity) -> dict:
    """Extract representation-specific style dict from a typed entity object.

    The returned dict is passed as ``representation_style`` to
    ``_add_visual_representation``.  Keys: shade_color, frame_color,
    frame_margin, frame_visible (Icon/ThemeLine), bg_color, filled,
    line_color, line_width (Box/Circle/EventFrame/TextBlock/Label),
    alignment, width, height (TextBlock/Label), diameter, autosize (Circle),
    depth (Box).  Only keys that are not None are included.
    """
    from .colors import color_to_colorref
    style = {}

    # shade_color (Icon, ThemeLine, EventFrame — maps to IconShadingColour)
    shade = getattr(entity, 'shade_color', None) or getattr(entity, 'color', None)
    if shade is not None:
        # Unwrap Color enum (str-Enum subclass) before stringifying
        if hasattr(shade, 'value'):
            shade = shade.value
        if isinstance(shade, int):
            style['shade_color'] = shade
        else:
            s = str(shade).strip()
            if s:
                style['shade_color'] = color_to_colorref(s)

    # frame fields (Icon, ThemeLine — uses nested Frame dataclass)
    frame_obj = getattr(entity, 'frame', None)
    if frame_obj is not None:
        if frame_obj.color is not None:
            style['frame_color'] = color_to_colorref(frame_obj.color)
        if frame_obj.margin is not None:
            style['frame_margin'] = frame_obj.margin
        if frame_obj.visible is not None:
            style['frame_visible'] = frame_obj.visible

    # Color-typed shape fields need normalization through color_to_colorref
    # so that named colors, hex strings, and Color enums all work uniformly.
    _COLOR_FIELDS = ('bg_color', 'line_color')
    for field in _COLOR_FIELDS:
        val = getattr(entity, field, None)
        if val is not None:
            style[field] = color_to_colorref(val)

    # Plain shape fields (Box, Circle, EventFrame, TextBlock, Label)
    for field in ('filled', 'line_width', 'alignment', 'width', 'height',
                  'diameter', 'autosize', 'depth'):
        val = getattr(entity, field, None)
        if val is not None:
            style[field] = val

    # Icon text offset fields
    for field in ('text_x', 'text_y'):
        val = getattr(entity, field, None)
        if val is not None:
            style[field] = val

    # Enlargement (Icon, EventFrame, ThemeLine)
    enl = getattr(entity, 'enlargement', None)
    if enl is not None:
        style['enlargement'] = _resolve_enum(enl, _ENLARGE_MAP)

    # Per-entity icon override (Icon, EventFrame, ThemeLine)
    icon_name = getattr(entity, 'icon', None)
    if icon_name is not None:
        style['type_icon_name'] = str(icon_name)

    return style


def _icon_text_attrs(style: Dict) -> Dict[str, str]:
    """Build <Icon> attributes dict, only including TextX/TextY when explicitly set."""
    attrs: Dict[str, str] = {}
    if style.get('text_x') is not None:
        attrs['TextX'] = str(int(style['text_x']))
    if style.get('text_y') is not None:
        attrs['TextY'] = str(int(style['text_y']))
    return attrs


def _maybe_frame_style(parent: ET.Element, style: Dict) -> None:
    """Append a <FrameStyle> child only when at least one frame field is explicitly set."""
    has_any = any(k in style for k in ('frame_color', 'frame_margin', 'frame_visible'))
    if not has_any:
        return
    ET.SubElement(parent, 'FrameStyle', {
        'Colour':  str(int(style.get('frame_color', 16764057))),
        'Margin':  str(int(style.get('frame_margin', 2))),
        'Visible': 'true' if style.get('frame_visible', False) else 'false',
    })


# Map Font dataclass field name → (xml_attr, type_tag)
_FONT_DC_FIELD_MAP: List[Tuple[str, str, str]] = [
    ('name',       'FaceName',   'str'),
    ('size',       'PointSize',  'int'),
    ('color',      'FontColour', 'color'),
    ('bg_color',   'BackColour', 'color'),
    ('bold',       'Bold',       'bool'),
    ('italic',     'Italic',     'bool'),
    ('strikeout',  'Strikeout',  'bool'),
    ('underline',  'Underline',  'bool'),
]


def _font_overrides_from_dc(font: Any) -> Dict[str, str]:
    """Extract font XML attribute overrides from a ``Font`` dataclass instance.

    Returns a dict of XML attr name → str value, only including fields the user
    explicitly set (not None).
    """
    if font is None:
        return {}
    out: Dict[str, str] = {}
    for fld_name, xml_attr, type_tag in _FONT_DC_FIELD_MAP:
        val = getattr(font, fld_name, None)
        if val is None:
            continue
        if type_tag == 'bool':
            out[xml_attr] = 'true' if val else 'false'
        elif type_tag == 'int':
            out[xml_attr] = str(int(val))
        elif type_tag == 'color':
            if isinstance(val, int):
                out[xml_attr] = str(val)
            else:
                # color_to_colorref unwraps Color enums and accepts strings
                out[xml_attr] = str(color_to_colorref(val))
        else:
            out[xml_attr] = str(val)
    return out


class ANXBuilder:
    """Converts a batch of (DataFrame, entities, links) records to ANX XML."""

    @staticmethod
    def _font_el(
        parent: ET.Element,
        defaults: Dict[str, str],
        overrides: Dict[str, str],
    ) -> ET.Element:
        """Append a <Font> child to *parent* merging *defaults* with *overrides*."""
        attrs = {**defaults, **overrides}
        return ET.SubElement(parent, 'Font', attrs)

    # ── Construction ─────────────────────────────────────────────────────────

    def __init__(self) -> None:
        self._id_ctr: int = 0

        # Registry: name → xml-id
        self._entity_types:    Dict[str, str] = {}
        self._link_types:      Dict[str, str] = {}
        self._att_classes:     Dict[str, Tuple[str, str]] = {}  # name → (id, att_type)
        self._att_class_icons: Dict[str, str] = {}              # name → IconFile
        self._strengths:       Dict[str, str] = {'Default': self._next_id()}
        self._strength_dot_styles: Dict[str, str] = {'Default': 'DotStyleSolid'}  # name → DotStyle
        self._default_strength: str = 'Default'
        self._datetime_formats:   Dict[str, Tuple[str, str]] = {}  # name → (id, format_string)

        # Per-entity-type registry: name → dict with optional keys:
        #   pref_rep, icon_file, color, shade_color
        self._etype_meta:      Dict[str, Dict[str, Any]] = {}
        # Per-link-type registry: name → {color, semantic_type}
        self._ltype_meta:      Dict[str, Dict[str, Any]] = {}

        # Entity deduplication: identity → (chart_item_id, entity_int_id)
        self._entity_registry: Dict[str, Tuple[str, int]] = {}
        self._entity_int_ctr:  int = 0  # sequential integer for EntityId

        # Layout positions: identity → (x, y)
        self._positions:       Dict[str, Tuple[int, int]] = {}

        # Connection style dedup: sorted_pair → style_tuple (first link wins)
        self._pair_style: Dict[Tuple[str, str], Tuple[Optional[str], Optional[int], Optional[str]]] = {}
        # style_tuple → Connection Id (dedup across all pairs)
        self._style_conn: Dict[Tuple[Optional[str], Optional[int], Optional[str]], str] = {}
        # Fast-path flag: True when any link sets multiplicity/fan_out/theme_wiring
        self._has_conn_fields: bool = False

        # Accumulated XML elements (in order of insertion)
        self._chart_item_elements: List[ET.Element] = []

        # Resolved items (compute-then-emit architecture)
        self._resolved_items: List = []  # List[ResolvedEntity | ResolvedLink]

        # Build timer (set during build() for external access)
        self._build_timer: Optional[PhaseTimer] = None


    # ── ID management ────────────────────────────────────────────────────────

    def _next_id(self) -> str:
        self._id_ctr += 1
        return f'ID{self._id_ctr}'

    def _strength_id(self, name: str = 'Default') -> str:
        if name not in self._strengths:
            self._strengths[name] = self._next_id()
        return self._strengths[name]

    def register_strength(self, name: str, dot_style: str) -> None:
        """Register a named strength with its DotStyle.  First registration wins."""
        self._strength_id(name)  # ensure it has an ID
        if name not in self._strength_dot_styles:
            self._strength_dot_styles[name] = dot_style

    def replace_default_strength(self, new_name: str) -> None:
        """Replace the pre-seeded 'Default' strength with *new_name*.

        Updates internal registries so resolved entities/links that fall back to
        the default strength use the new name instead of 'Default'.
        """
        old_id = self._strengths.pop('Default', None)
        self._strength_dot_styles.pop('Default', None)
        if old_id:
            self._strengths[new_name] = old_id
            self._strength_dot_styles[new_name] = 'DotStyleSolid'
        self._default_strength = new_name

    def register_datetime_format(self, name: str, format_str: str = '') -> str:
        """Register a named DateTimeFormat. First registration wins. Returns the Id."""
        if name not in self._datetime_formats:
            self._datetime_formats[name] = (self._next_id(), format_str)
        return self._datetime_formats[name][0]

    def _entity_type_id(
        self,
        name: str,
        representation: Optional[Representation] = None,
        icon_file: Optional[str] = None,
        color: Optional[int] = None,
        shade_color: Optional[int] = None,
        semantic_type: Optional[str] = None,
    ) -> str:
        if name not in self._entity_types:
            eid = self._next_id()
            self._entity_types[name] = eid
            meta: Dict[str, Any] = {}
            if representation is not None:
                rep = representation
                pref_rep = _PREFERRED_REP.get(_enum_val(rep), 'RepresentAsIcon')
                meta['pref_rep'] = pref_rep
            if icon_file is not None:
                meta['icon_file'] = icon_file
            if color is not None:
                meta['color'] = color
            if shade_color is not None:
                meta['shade_color'] = shade_color
            if semantic_type is not None:
                meta['semantic_type'] = semantic_type
            self._etype_meta[name] = meta
        return self._entity_types[name]

    def _link_type_id(self, name: str, color: Optional[int] = None, semantic_type: Optional[str] = None) -> str:
        if name not in self._link_types:
            self._link_types[name] = self._next_id()
            self._ltype_meta[name] = {'color': color, 'semantic_type': semantic_type}
        return self._link_types[name]

    def _att_class_id(self, name: str, att_type: str = 'AttText') -> str:
        """Register an attribute class name and return its XML Id.

        First-write-wins: type conflicts (data-vs-data or config-vs-data) are
        caught by ``validate_attribute_classes`` *before* ``build()`` ever runs.
        This method no longer raises — it is a pure registration helper.
        """
        if name not in self._att_classes:
            self._att_classes[name] = (self._next_id(), att_type)
        return self._att_classes[name][0]

    def set_att_class_icon(self, name: str, icon_file: str) -> None:
        """Set the IconFile for an AttributeClass by name.

        First registration wins; subsequent calls for the same name are no-ops.
        """
        if name not in self._att_class_icons:
            self._att_class_icons[name] = icon_file

    # ── Entity/identity lookup ────────────────────────────────────────────────

    def _lookup_entity(self, identity: str) -> Optional[Tuple[str, int]]:
        """Look up (chart_item_id, entity_int_id) by entity identity string."""
        return self._entity_registry.get(str(identity))

    # ── Typed object entry points ─────────────────────────────────────────────

    def add_entity(self, entity) -> Optional[Tuple[str, int]]:
        """Register a single typed entity object.

        Accepts any _BaseEntity subclass: Icon, Box, Circle, ThemeLine,
        EventFrame, TextBlock, Label.
        Returns (chart_item_id, entity_int_id) or None if id is empty.
        """
        identity = str(entity.id) if entity.id else ''
        if not identity:
            return None
        if identity in self._entity_registry:
            return self._entity_registry[identity]

        resolved = self.resolve_entity(entity)
        if resolved is None:
            return self._entity_registry.get(identity)

        self._resolved_items.append(resolved)
        return (resolved.ci_id, resolved.entity_int_id)

    def add_link(self, link: Link) -> None:
        """Register a single typed Link object.

        Resolves from_id/to_id against the entity registry.
        Both entities must have been added before this link.
        Raises ValueError if either entity is not found.
        """
        resolved = self.resolve_link(link)
        self._resolved_items.append(resolved)

    # ── Resolve methods (compute-then-emit architecture) ────────────────────

    def _resolve_card(self, card) -> 'ResolvedCard':
        """Resolve a Card object into a ResolvedCard with parsed datetime."""
        from .resolved import ResolvedCard
        date_set, time_set, dt_str = self._format_datetime(card.date, card.time)
        return ResolvedCard(
            summary=card.summary,
            date_set=date_set,
            time_set=time_set,
            datetime_str=dt_str,
            datetime_description=card.datetime_description,
            source_ref=card.source_ref,
            source_type=card.source_type,
            description=card.description,
            grade_one=card.grade_one,
            grade_two=card.grade_two,
            grade_three=card.grade_three,
            timezone_id=card.timezone.id if card.timezone else None,
            timezone_name=card.timezone.name if card.timezone else None,
        )

    def _resolve_font_color(self, val) -> Optional[int]:
        """Resolve a font color value to COLORREF int or None."""
        if val is None:
            return None
        # Unwrap Color enum (str-Enum) before further checks
        if hasattr(val, 'value'):
            val = val.value
        if isinstance(val, float) and math.isnan(val):
            return None
        if isinstance(val, bool):
            return None
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val).strip()
        if not s:
            return None
        return color_to_colorref(s)

    def resolve_entity(self, entity, extra_cards=None,
                       semantic_guid=None) -> Optional['ResolvedEntity']:
        """Resolve a typed entity object into a ResolvedEntity.

        Handles entity dedup, attribute class registration, strength
        registration, icon name translation, datetime parsing, card
        resolution, and font color resolution.  Returns None if the entity
        has no id or was already registered (dedup).

        Args:
            extra_cards: additional Card objects (e.g. loose cards) to merge
                with inline cards — avoids mutating the user's entity object.
            semantic_guid: pre-resolved semantic GUID string — avoids
                monkey-patching the user's entity object.

        Side effects: mutates _entity_registry, _att_classes, _strengths,
        _entity_int_ctr.
        """
        from .resolved import ResolvedEntity, ResolvedAttr

        identity = str(entity.id) if entity.id else ''
        if not identity:
            return None
        entity_type = str(entity.type) if entity.type else 'Entity'

        if identity in self._entity_registry:
            return None  # dedup — already registered

        ci_id = self._next_id()
        self._entity_int_ctr += 1
        entity_int_id = self._entity_int_ctr
        self._entity_registry[identity] = (ci_id, entity_int_id)

        rep = _entity_rep(entity)
        strength = entity.strength or self._default_strength
        self._strength_id(strength)

        # Attributes → ResolvedAttr(class_name, ac_ref_id, value_str)
        raw_attrs = _parse_attrs(entity.attributes or {})
        resolved_attrs: List[ResolvedAttr] = []
        for name, value, type_str in raw_attrs:
            att_type = _ATT_TYPE.get(type_str, 'AttText')
            ref_id = self._att_class_id(name, att_type)
            resolved_attrs.append(ResolvedAttr(name, ref_id, value))

        # Representation style + icon name translation
        representation_style = _entity_style(entity)
        representation_style['strength'] = strength
        if 'type_icon_name' in representation_style:
            meta = self._etype_meta.get(representation_style['type_icon_name'])
            if meta and meta.get('icon_file'):
                representation_style['type_icon_name'] = meta['icon_file']

        # Datetime
        date_set, time_set, dt_str = self._format_datetime(entity.date, entity.time)

        # Cards (inline + extra loose cards — no mutation of user object)
        all_cards = list(entity.cards or []) + (extra_cards or [])
        resolved_cards = [self._resolve_card(c) for c in all_cards]

        return ResolvedEntity(
            ci_id=ci_id,
            label=str(entity.label) if entity.label is not None else identity,
            description=str(entity.description or ''),
            date_set=date_set,
            time_set=time_set,
            datetime_str=dt_str,
            datetime_description=str(entity.datetime_description or ''),
            ordered=entity.ordered or False,
            source_ref=str(entity.source_ref or ''),
            source_type=str(entity.source_type or ''),
            grade_one=entity.grade_one,
            grade_two=entity.grade_two,
            grade_three=entity.grade_three,
            attributes=resolved_attrs,
            cards=resolved_cards,
            strength=strength,
            background=entity.background,
            show_datetime_description=entity.show_datetime_description,
            sub_text_width=entity.sub_text_width,
            use_sub_text_width=entity.use_sub_text_width,
            datetime_format=entity.datetime_format,
            label_color=self._resolve_font_color(entity.label_font.color),
            label_bg_color=self._resolve_font_color(entity.label_font.bg_color),
            label_face=entity.label_font.name,
            label_size=entity.label_font.size,
            label_bold=entity.label_font.bold,
            label_italic=entity.label_font.italic,
            label_strikeout=entity.label_font.strikeout,
            label_underline=entity.label_font.underline,
            show_description=entity.show.description,
            show_grades=entity.show.grades,
            show_label=entity.show.label,
            show_date=entity.show.date,
            show_source_ref=entity.show.source_ref,
            show_source_type=entity.show.source_type,
            show_pin=entity.show.pin,
            timezone=entity.timezone,
            entity_int_id=entity_int_id,
            identity=identity,
            entity_type=entity_type,
            representation=rep.value,
            representation_style=representation_style,
            semantic_guid=semantic_guid,
            x=0, y=0,
        )

    def resolve_link(self, link: Link, extra_cards=None,
                     semantic_guid=None) -> 'ResolvedLink':
        """Resolve a typed Link object into a ResolvedLink.

        Resolves from/to entities, arrow enum, line color, connection style,
        attribute classes, datetime, cards, and font colors.

        Args:
            extra_cards: additional Card objects (e.g. loose cards) to merge
                with inline cards — avoids mutating the user's link object.
            semantic_guid: pre-resolved semantic GUID string — avoids
                monkey-patching the user's link object.

        Side effects: mutates _link_types, _att_classes, _strengths,
        _pair_style, _style_conn, _has_conn_fields.
        Raises ValueError if from_id or to_id not found.
        """
        from .resolved import ResolvedLink, ResolvedAttr

        from_info = self._lookup_entity(str(link.from_id))
        to_info   = self._lookup_entity(str(link.to_id))
        if from_info is None:
            raise ValueError(
                f"Link references unknown entity '{link.from_id}' (from_id). "
                f"Add the entity first."
            )
        if to_info is None:
            raise ValueError(
                f"Link references unknown entity '{link.to_id}' (to_id). "
                f"Add the entity first."
            )
        from_ci_id, from_int_id = from_info
        to_ci_id, to_int_id = to_info

        link_type = str(link.type or 'Link')
        self._link_type_id(link_type)
        strength = str(link.strength or self._default_strength)
        self._strength_id(strength)

        # Connection style — single-pass dict lookup
        _mult = _enum_val(link.multiplicity) or None
        _tw = _enum_val(link.theme_wiring) or None
        style = (_mult, link.fan_out, _tw)
        conn_id: Optional[str] = None
        if any(v is not None for v in style):
            self._has_conn_fields = True
            pair = tuple(sorted((from_ci_id, to_ci_id)))
            if pair not in self._pair_style:
                self._pair_style[pair] = style
            if style not in self._style_conn:
                self._style_conn[style] = self._next_id()
            conn_id = self._style_conn[style]

        # Attributes → ResolvedAttr(class_name, ac_ref_id, value_str)
        raw_attrs = _parse_attrs(link.attributes or {})
        resolved_attrs: List[ResolvedAttr] = []
        for name, value, type_str in raw_attrs:
            att_type = _ATT_TYPE.get(type_str, 'AttText')
            ref_id = self._att_class_id(name, att_type)
            resolved_attrs.append(ResolvedAttr(name, ref_id, value))

        arrow = _resolve_enum(link.arrow, _ARROW_MAP) if link.arrow else 'ArrowNone'
        ci_id = self._next_id()

        # Datetime
        date_set, time_set, dt_str = self._format_datetime(link.date, link.time)

        # Cards (inline + extra loose cards — no mutation of user object)
        all_cards = list(link.cards or []) + (extra_cards or [])
        resolved_cards = [self._resolve_card(c) for c in all_cards]

        return ResolvedLink(
            ci_id=ci_id,
            label=str(link.label or ''),
            description=str(link.description or ''),
            date_set=date_set,
            time_set=time_set,
            datetime_str=dt_str,
            datetime_description=str(link.datetime_description or ''),
            ordered=link.ordered or False,
            source_ref=str(link.source_ref or ''),
            source_type=str(link.source_type or ''),
            grade_one=link.grade_one,
            grade_two=link.grade_two,
            grade_three=link.grade_three,
            attributes=resolved_attrs,
            cards=resolved_cards,
            strength=strength,
            background=link.background,
            show_datetime_description=link.show_datetime_description,
            sub_text_width=link.sub_text_width,
            use_sub_text_width=link.use_sub_text_width,
            datetime_format=link.datetime_format,
            label_color=self._resolve_font_color(link.label_font.color),
            label_bg_color=self._resolve_font_color(link.label_font.bg_color),
            label_face=link.label_font.name,
            label_size=link.label_font.size,
            label_bold=link.label_font.bold,
            label_italic=link.label_font.italic,
            label_strikeout=link.label_font.strikeout,
            label_underline=link.label_font.underline,
            show_description=link.show.description,
            show_grades=link.show.grades,
            show_label=link.show.label,
            show_date=link.show.date,
            show_source_ref=link.show.source_ref,
            show_source_type=link.show.source_type,
            show_pin=link.show.pin,
            timezone=link.timezone,
            from_int_id=from_int_id,
            to_int_id=to_int_id,
            from_ci_id=from_ci_id,
            to_ci_id=to_ci_id,
            link_type=link_type,
            arrow=arrow,
            line_width=link.line_width if link.line_width is not None else 1,
            line_color=color_to_colorref(link.line_color) if link.line_color is not None else 0,
            offset=link.offset if link.offset is not None else 0,
            conn_id=conn_id,
            semantic_guid=semantic_guid,
        )

    # ── Emit methods (create XML from resolved dataclasses) ──────────────────

    def _emit_resolved_card(self, parent: ET.Element, card: 'ResolvedCard') -> None:
        """Build a Card XML element from a ResolvedCard (pre-parsed datetime)."""
        attribs: Dict[str, str] = {}
        if card.summary:
            attribs['Summary'] = str(card.summary)
        if card.date_set:
            attribs['DateSet'] = 'true'
        if card.time_set:
            attribs['TimeSet'] = 'true'
        if card.datetime_str:
            attribs['DateTime'] = card.datetime_str
        if card.grade_one is not None:
            attribs['GradeOneIndex'] = str(card.grade_one)
        if card.grade_two is not None:
            attribs['GradeTwoIndex'] = str(card.grade_two)
        if card.grade_three is not None:
            attribs['GradeThreeIndex'] = str(card.grade_three)
        for attr_name, xml_attr in (('source_ref', 'SourceReference'),
                                     ('source_type', 'SourceType'),
                                     ('description', 'Text'),
                                     ('datetime_description', 'DateTimeDescription')):
            val = getattr(card, attr_name)
            if val:
                attribs[xml_attr] = str(val)

        card_el = ET.SubElement(parent, 'Card', attribs)
        if card.timezone_id is not None or card.timezone_name:
            tz_attrs: Dict[str, str] = {}
            if card.timezone_id is not None:
                tz_attrs['UniqueID'] = str(card.timezone_id)
            if card.timezone_name:
                tz_attrs['Name'] = str(card.timezone_name)
            ET.SubElement(card_el, 'TimeZone', tz_attrs)

    def emit_entity(self, re: 'ResolvedEntity') -> None:
        """Create XML from a ResolvedEntity and store in _chart_item_elements."""
        # Convert resolved attrs back to _AttrTuple for existing _add_attributes
        anb_attrs = [
            _AttrTuple(class_name=name, value=value, attr_type=AttributeType.TEXT)
            for name, _ref_id, value in re.attributes
        ]

        ci_el = self._make_entity_chart_item(
            ci_id=re.ci_id,
            entity_int_id=re.entity_int_id,
            identity=re.identity,
            label=re.label,
            entity_type=re.entity_type,
            rep=Representation(re.representation),
            description=re.description,
            date_val=None, time_val=None,
            _parsed_dt=(re.date_set, re.time_set, re.datetime_str),
            source_ref=re.source_ref,
            source_type=re.source_type,
            grade_one=re.grade_one,
            grade_two=re.grade_two,
            grade_three=re.grade_three,
            is_controlling=re.ordered,
            attributes=anb_attrs,
            label_color=re.label_color,
            label_bg_color=re.label_bg_color,
            label_face=re.label_face,
            label_size=re.label_size,
            label_bold=re.label_bold,
            label_italic=re.label_italic,
            label_strikeout=re.label_strikeout,
            label_underline=re.label_underline,
            representation_style=re.representation_style,
            subitem_description=re.show_description,
            subitem_grades=re.show_grades,
            subitem_label=re.show_label,
            subitem_date=re.show_date,
            subitem_source_ref=re.show_source_ref,
            subitem_source_type=re.show_source_type,
            subitem_pin=re.show_pin,
            timezone=re.timezone,
            background=re.background,
            datetime_description=re.datetime_description,
            show_datetime_description=re.show_datetime_description,
            sub_text_width=re.sub_text_width,
            use_sub_text_width=re.use_sub_text_width,
            datetime_format=re.datetime_format,
        )

        # Apply layout position from resolved entity
        if re.x or re.y:
            ci_el.set('XPosition', str(re.x))
            end_el = ci_el.find('End')
            if end_el is not None:
                end_el.set('X', str(re.x))
                end_el.set('Y', str(re.y))

        # Per-instance SemanticTypeGuid on <Entity> element
        if re.semantic_guid:
            entity_el = ci_el.find('./End/Entity')
            if entity_el is not None:
                entity_el.set('SemanticTypeGuid', re.semantic_guid)

        # Attach resolved cards
        if re.cards:
            entity_el = ci_el.find('./End/Entity')
            if entity_el is not None:
                card_coll = ET.SubElement(entity_el, 'CardCollection')
                for card in re.cards:
                    self._emit_resolved_card(card_coll, card)

        self._chart_item_elements.append(ci_el)

    def emit_link(self, rl: 'ResolvedLink') -> None:
        """Create XML from a ResolvedLink and store in _chart_item_elements."""
        # Convert resolved attrs back to _AttrTuple for existing _add_attributes
        anb_attrs = [
            _AttrTuple(class_name=name, value=value, attr_type=AttributeType.TEXT)
            for name, _ref_id, value in rl.attributes
        ]

        ci_el = self._make_link_chart_item(
            ci_id=rl.ci_id,
            label=rl.label,
            description=rl.description,
            date_val=None, time_val=None,
            _parsed_dt=(rl.date_set, rl.time_set, rl.datetime_str),
            source_ref=rl.source_ref,
            source_type=rl.source_type,
            from_int_id=rl.from_int_id,
            to_int_id=rl.to_int_id,
            link_type=rl.link_type,
            arrow=rl.arrow,
            line_width=rl.line_width,
            strength=rl.strength,
            grade_one=rl.grade_one,
            grade_two=rl.grade_two,
            grade_three=rl.grade_three,
            is_controlling=rl.ordered,
            attributes=anb_attrs,
            cards=rl.cards,
            line_color=rl.line_color,
            label_color=rl.label_color,
            label_bg_color=rl.label_bg_color,
            label_face=rl.label_face,
            label_size=rl.label_size,
            label_bold=rl.label_bold,
            label_italic=rl.label_italic,
            label_strikeout=rl.label_strikeout,
            label_underline=rl.label_underline,
            offset=rl.offset,
            subitem_description=rl.show_description,
            subitem_grades=rl.show_grades,
            subitem_label=rl.show_label,
            subitem_date=rl.show_date,
            subitem_source_ref=rl.show_source_ref,
            subitem_source_type=rl.show_source_type,
            subitem_pin=rl.show_pin,
            timezone=rl.timezone,
            background=rl.background,
            datetime_description=rl.datetime_description,
            show_datetime_description=rl.show_datetime_description,
            sub_text_width=rl.sub_text_width,
            use_sub_text_width=rl.use_sub_text_width,
            datetime_format=rl.datetime_format,
            conn_id=rl.conn_id,
        )

        # Per-instance SemanticTypeGuid on <Link> element
        if rl.semantic_guid:
            link_el = ci_el.find('Link')
            if link_el is not None:
                link_el.set('SemanticTypeGuid', rl.semantic_guid)

        self._chart_item_elements.append(ci_el)

    # ── XML element builders ──────────────────────────────────────────────────

    def _make_entity_chart_item(
        self,
        ci_id: str,
        entity_int_id: int,
        identity: str,
        label: str,
        entity_type: str,
        rep: Representation,
        description: str,
        date_val: Optional[str],
        time_val: Optional[str],
        source_ref: str,
        source_type: str,
        grade_one: Optional[int],
        grade_two: Optional[int],
        grade_three: Optional[int],
        is_controlling: bool,
        attributes: List[_AttrTuple],
        label_color: Any = None,
        label_bg_color: Any = None,
        label_face: Any = None,
        label_size: Any = None,
        label_bold: Any = None,
        label_italic: Any = None,
        label_strikeout: Any = None,
        label_underline: Any = None,
        representation_style: Optional[Dict] = None,
        subitem_description: Any = None,
        subitem_grades: Any = None,
        subitem_label: Any = None,
        subitem_date: Any = None,
        subitem_source_ref: Any = None,
        subitem_source_type: Any = None,
        subitem_pin: Any = None,
        timezone: Any = None,
        background: Any = None,
        datetime_description: Any = None,
        show_datetime_description: Any = None,
        sub_text_width: Any = None,
        use_sub_text_width: Any = None,
        datetime_format: Any = None,
        _parsed_dt: Optional[Tuple[bool, bool, Optional[str]]] = None,
    ) -> ET.Element:
        if _parsed_dt is not None:
            date_set, time_set, dt_str = _parsed_dt
        else:
            date_set, time_set, dt_str = self._format_datetime(date_val, time_val)

        ci_attribs: Dict[str, str] = {'Id': ci_id, 'Label': label}
        if description:
            ci_attribs['Description'] = description
        if date_set:
            ci_attribs['DateSet'] = 'true'
        if time_set:
            ci_attribs['TimeSet'] = 'true'
        if is_controlling:
            ci_attribs['Ordered'] = 'true'
        if source_ref:
            ci_attribs['SourceReference'] = source_ref
        if source_type:
            ci_attribs['SourceType'] = source_type
        if grade_one is not None:
            ci_attribs['GradeOneIndex'] = str(grade_one)
        if grade_two is not None:
            ci_attribs['GradeTwoIndex'] = str(grade_two)
        if grade_three is not None:
            ci_attribs['GradeThreeIndex'] = str(grade_three)
        if dt_str:
            ci_attribs['DateTime'] = dt_str
        if datetime_description:
            ci_attribs['DateTimeDescription'] = str(datetime_description)

        ci_el = ET.Element('ChartItem', ci_attribs)

        # End > Entity > visual representation
        end_el = ET.SubElement(ci_el, 'End', {'X': '0', 'Y': '0', 'Z': '0'})
        entity_el = ET.SubElement(end_el, 'Entity', {
            'EntityId': str(entity_int_id),
            'Identity': identity,
            'LabelIsIdentity': 'true' if label == identity else 'false',
        })
        self._add_visual_representation(entity_el, rep, entity_type, style=representation_style or {})

        # Attributes
        if attributes:
            self._add_attributes(ci_el, attributes)

        # Style (must come before TimeZone — XSD order: End → AttributeCollection → CIStyle → TimeZone)
        self._add_ci_style(
            ci_el,
            background=background,
            show_datetime_description=show_datetime_description,
            sub_text_width=sub_text_width,
            use_sub_text_width=use_sub_text_width,
            label_color=label_color,
            label_bg_color=label_bg_color,
            label_face=label_face,
            label_size=label_size,
            label_bold=label_bold,
            label_italic=label_italic,
            label_strikeout=label_strikeout,
            label_underline=label_underline,
            subitem_description=subitem_description,
            subitem_grades=subitem_grades,
            subitem_label=subitem_label,
            subitem_date=subitem_date,
            subitem_source_ref=subitem_source_ref,
            subitem_source_type=subitem_source_type,
            subitem_pin=subitem_pin,
            datetime_format=datetime_format,
        )

        # TimeZone on ChartItem — must come after CIStyle per XSD sequence
        if timezone is not None and not (isinstance(timezone, float) and math.isnan(timezone)):
            tz_attrs: Dict[str, str] = {}
            if hasattr(timezone, 'id') and hasattr(timezone, 'name'):
                # TimeZone dataclass
                if timezone.id is not None:
                    tz_attrs['UniqueID'] = str(timezone.id)
                if timezone.name:
                    tz_attrs['Name'] = str(timezone.name)
            elif isinstance(timezone, dict):
                if 'id' in timezone and timezone['id'] is not None:
                    tz_attrs['UniqueID'] = str(timezone['id'])
                if timezone.get('name'):
                    tz_attrs['Name'] = str(timezone['name'])
            else:
                tz_attrs['UniqueID'] = str(timezone)
            ET.SubElement(ci_el, 'TimeZone', tz_attrs)

        return ci_el

    def _make_link_chart_item(
        self,
        ci_id: str,
        label: str,
        description: str,
        date_val: Optional[str],
        time_val: Optional[str],
        source_ref: str,
        source_type: str,
        from_int_id: int,
        to_int_id: int,
        link_type: str,
        arrow: str,
        line_width: int,
        strength: str,
        grade_one: Optional[int],
        grade_two: Optional[int],
        grade_three: Optional[int],
        is_controlling: bool,
        attributes: List[_AttrTuple],
        cards: Optional[List] = None,
        line_color: int = 0,
        label_color: Any = None,
        label_bg_color: Any = None,
        label_face: Any = None,
        label_size: Any = None,
        label_bold: Any = None,
        label_italic: Any = None,
        label_strikeout: Any = None,
        label_underline: Any = None,
        offset: int = 0,
        subitem_description: Any = None,
        subitem_grades: Any = None,
        subitem_label: Any = None,
        subitem_date: Any = None,
        subitem_source_ref: Any = None,
        subitem_source_type: Any = None,
        subitem_pin: Any = None,
        timezone: Any = None,
        background: Any = None,
        datetime_description: Any = None,
        show_datetime_description: Any = None,
        sub_text_width: Any = None,
        use_sub_text_width: Any = None,
        datetime_format: Any = None,
        conn_id: Optional[str] = None,
        _parsed_dt: Optional[Tuple[bool, bool, Optional[str]]] = None,
    ) -> ET.Element:
        if _parsed_dt is not None:
            date_set, time_set, dt_str = _parsed_dt
        else:
            date_set, time_set, dt_str = self._format_datetime(date_val, time_val)

        ci_attribs: Dict[str, str] = {'Id': ci_id, 'Label': label}
        if description:
            ci_attribs['Description'] = description
        if date_set:
            ci_attribs['DateSet'] = 'true'
        if time_set:
            ci_attribs['TimeSet'] = 'true'
        if is_controlling:
            ci_attribs['Ordered'] = 'true'
        if source_ref:
            ci_attribs['SourceReference'] = source_ref
        if source_type:
            ci_attribs['SourceType'] = source_type
        if grade_one is not None:
            ci_attribs['GradeOneIndex'] = str(grade_one)
        if grade_two is not None:
            ci_attribs['GradeTwoIndex'] = str(grade_two)
        if grade_three is not None:
            ci_attribs['GradeThreeIndex'] = str(grade_three)
        if dt_str:
            ci_attribs['DateTime'] = dt_str
        if datetime_description:
            ci_attribs['DateTimeDescription'] = str(datetime_description)

        ci_el = ET.Element('ChartItem', ci_attribs)

        link_attrs: Dict[str, str] = {
            'End1Id': str(from_int_id),
            'End2Id': str(to_int_id),
        }
        if offset:
            link_attrs['Offset'] = str(offset)
        if conn_id:
            link_attrs['ConnectionReference'] = conn_id
        link_el = ET.SubElement(ci_el, 'Link', link_attrs)

        if cards:
            card_coll = ET.SubElement(link_el, 'CardCollection')
            for card in cards:
                self._emit_resolved_card(card_coll, card)

        ls_attrs: Dict[str, str] = {'Strength': strength}
        if arrow and arrow != 'ArrowNone':
            ls_attrs['ArrowStyle'] = arrow
        if line_width and line_width != 1:
            ls_attrs['LineWidth'] = str(line_width)
        if line_color:
            ls_attrs['LineColour'] = str(line_color)
        if link_type:
            ls_attrs['Type'] = link_type
            ls_attrs['LinkTypeReference'] = self._link_types[link_type]
        ET.SubElement(link_el, 'LinkStyle', ls_attrs)

        if attributes:
            self._add_attributes(ci_el, attributes)

        # Style (must come before TimeZone — XSD order: Link → AttributeCollection → CIStyle → TimeZone)
        self._add_ci_style(
            ci_el,
            background=background,
            show_datetime_description=show_datetime_description,
            sub_text_width=sub_text_width,
            use_sub_text_width=use_sub_text_width,
            label_color=label_color,
            label_bg_color=label_bg_color,
            label_face=label_face,
            label_size=label_size,
            label_bold=label_bold,
            label_italic=label_italic,
            label_strikeout=label_strikeout,
            label_underline=label_underline,
            subitem_description=subitem_description,
            subitem_grades=subitem_grades,
            subitem_label=subitem_label,
            subitem_date=subitem_date,
            subitem_source_ref=subitem_source_ref,
            subitem_source_type=subitem_source_type,
            subitem_pin=subitem_pin,
            datetime_format=datetime_format,
        )

        # TimeZone on ChartItem — must come after CIStyle per XSD sequence
        if timezone is not None and not (isinstance(timezone, float) and math.isnan(timezone)):
            tz_attrs: Dict[str, str] = {}
            if hasattr(timezone, 'id') and hasattr(timezone, 'name'):
                # TimeZone dataclass
                if timezone.id is not None:
                    tz_attrs['UniqueID'] = str(timezone.id)
                if timezone.name:
                    tz_attrs['Name'] = str(timezone.name)
            elif isinstance(timezone, dict):
                if 'id' in timezone and timezone['id'] is not None:
                    tz_attrs['UniqueID'] = str(timezone['id'])
                if timezone.get('name'):
                    tz_attrs['Name'] = str(timezone['name'])
            else:
                tz_attrs['UniqueID'] = str(timezone)
            ET.SubElement(ci_el, 'TimeZone', tz_attrs)

        return ci_el

    def _add_visual_representation(
        self, entity_el: ET.Element, rep: Representation, entity_type: str,
        style: Optional[Dict] = None,
    ) -> None:
        style = style or {}
        et_id = self._entity_types.get(entity_type)  # None if no pre-registered EntityType
        rep_val = _enum_val(rep)

        if rep_val == Representation.ICON.value:
            icon = ET.SubElement(entity_el, 'Icon', _icon_text_attrs(style))
            icon_style_attrs: Dict[str, str] = {
                'Type': entity_type,
            }
            if et_id:
                icon_style_attrs['EntityTypeReference'] = et_id
            if style.get('enlargement'):
                icon_style_attrs['Enlargement'] = style['enlargement']
            if style.get('shade_color'):
                icon_style_attrs['IconShadingColour'] = str(int(style['shade_color']))
            if style.get('type_icon_name'):
                icon_style_attrs['OverrideTypeIcon'] = 'true'
                icon_style_attrs['TypeIconName'] = style['type_icon_name']
            icon_style = ET.SubElement(icon, 'IconStyle', icon_style_attrs)
            _maybe_frame_style(icon_style, style)
        elif rep_val == Representation.BOX.value:
            bc    = str(style.get('bg_color', 16777215))
            sname = str(style.get('strength', 'Default'))
            box_attrs: Dict[str, str] = {}
            if 'width' in style:
                box_attrs['Width'] = str(int(style['width']))
            if 'height' in style:
                box_attrs['Height'] = str(int(style['height']))
            if 'depth' in style:
                box_attrs['Depth'] = str(int(style['depth']))
            box = ET.SubElement(entity_el, 'Box', box_attrs)
            box_style_attrs: Dict[str, str] = {'Strength': sname}
            if entity_type:
                box_style_attrs['Type'] = entity_type
            if et_id:
                box_style_attrs['EntityTypeReference'] = et_id
            if 'bg_color' in style:
                box_style_attrs['BackColour'] = str(style['bg_color'])
            if 'filled' in style:
                box_style_attrs['Filled'] = 'true' if style['filled'] else 'false'
            if 'line_width' in style:
                box_style_attrs['LineWidth'] = str(int(style['line_width']))
            ET.SubElement(box, 'BoxStyle', box_style_attrs)
        elif rep_val == Representation.CIRCLE.value:
            sname = str(style.get('strength', 'Default'))
            circle = ET.SubElement(entity_el, 'Circle')
            circle_style_attrs: Dict[str, str] = {'Strength': sname}
            if entity_type:
                circle_style_attrs['Type'] = entity_type
            if et_id:
                circle_style_attrs['EntityTypeReference'] = et_id
            if 'bg_color' in style:
                circle_style_attrs['BackColour'] = str(style['bg_color'])
            if 'filled' in style:
                circle_style_attrs['Filled'] = 'true' if style['filled'] else 'false'
            if 'line_width' in style:
                circle_style_attrs['LineWidth'] = str(int(style['line_width']))
            if 'diameter' in style:
                circle_style_attrs['Diameter'] = str(float(style['diameter']) / 100)
            if 'autosize' in style:
                circle_style_attrs['Autosize'] = 'true' if style['autosize'] else 'false'
            ET.SubElement(circle, 'CircleStyle', circle_style_attrs)
        elif rep_val == Representation.EVENT_FRAME.value:
            sname = str(style.get('strength', 'Default'))
            event_style_attrs: Dict[str, str] = {'Strength': sname}
            if entity_type:
                event_style_attrs['Type'] = entity_type
            if et_id:
                event_style_attrs['EntityTypeReference'] = et_id
            if 'bg_color' in style:
                event_style_attrs['BackColour'] = str(style['bg_color'])
            if 'filled' in style:
                event_style_attrs['Filled'] = 'true' if style['filled'] else 'false'
            if 'line_width' in style:
                event_style_attrs['LineWidth'] = str(int(style['line_width']))
            if style.get('enlargement'):
                event_style_attrs['Enlargement'] = style['enlargement']
            if style.get('shade_color'):
                event_style_attrs['IconShadingColour'] = str(int(style['shade_color']))
            if style.get('line_color') is not None:
                event_style_attrs['LineColour'] = str(int(style['line_color']))
            if style.get('type_icon_name'):
                event_style_attrs['OverrideTypeIcon'] = 'true'
                event_style_attrs['TypeIconName'] = style['type_icon_name']
            event = ET.SubElement(entity_el, 'Event')
            ET.SubElement(event, 'EventStyle', event_style_attrs)
        elif rep_val == Representation.TEXT_BLOCK.value:
            sname = str(style.get('strength', 'Default'))
            tb_attrs: Dict[str, str] = {'Strength': sname}
            if entity_type:
                tb_attrs['Type'] = entity_type
            if et_id:
                tb_attrs['EntityTypeReference'] = et_id
            if 'alignment' in style:
                tb_attrs['Alignment'] = _resolve_enum(style['alignment'], _TEXT_ALIGN_MAP)
            if 'bg_color' in style:
                tb_attrs['BackColour'] = str(style['bg_color'])
            if 'filled' in style:
                tb_attrs['Filled'] = 'true' if style['filled'] else 'false'
            if 'line_width' in style:
                tb_attrs['LineWidth'] = str(int(style['line_width']))
            if style.get('line_color') is not None:
                tb_attrs['LineColour'] = str(int(style['line_color']))
            if 'width' in style:
                tb_attrs['Width'] = str(float(style['width']) / 100)
            if 'height' in style:
                tb_attrs['Height'] = str(float(style['height']) / 100)
            tb = ET.SubElement(entity_el, 'TextBlock')
            ET.SubElement(tb, 'TextBlockStyle', tb_attrs)
        elif rep_val == Representation.LABEL.value:
            # Label uses <TextBlock>/<TextBlockStyle> (same element as TextBlock).
            # RepresentAsBorder in PreferredRepresentation distinguishes it at the type level.
            # BackColour, LineColour and Filled are always set to make the border/fill invisible
            # — approximating i2's native Label appearance.
            chart_bg = str(getattr(self, '_chart_bg_color', 16777215))
            sname    = str(style.get('strength', 'Default'))
            lbl_attrs: Dict[str, str] = {
                'Strength': sname,
                'BackColour': chart_bg,
                'Filled': 'false',
                'LineColour': chart_bg,
            }
            if entity_type:
                lbl_attrs['Type'] = entity_type
            if et_id:
                lbl_attrs['EntityTypeReference'] = et_id
            if 'alignment' in style:
                lbl_attrs['Alignment'] = _resolve_enum(style['alignment'], _TEXT_ALIGN_MAP)
            if 'line_width' in style:
                lbl_attrs['LineWidth'] = str(int(style['line_width']))
            if 'width' in style:
                lbl_attrs['Width'] = str(float(style['width']) / 100)
            if 'height' in style:
                lbl_attrs['Height'] = str(float(style['height']) / 100)
            lbl_tb = ET.SubElement(entity_el, 'TextBlock')
            ET.SubElement(lbl_tb, 'TextBlockStyle', lbl_attrs)
        elif rep_val == Representation.OLE_OBJECT.value:
            # OleItem is the confirmed valid child element (from ANB 9 schema error log).
            # Internal attributes/children not yet investigated — falls back to Icon.
            icon = ET.SubElement(entity_el, 'Icon', _icon_text_attrs(style))
            _ole_attrs: Dict[str, str] = {
                'Type': entity_type,
            }
            if et_id:
                _ole_attrs['EntityTypeReference'] = et_id
            if style.get('enlargement'):
                _ole_attrs['Enlargement'] = style['enlargement']
            ET.SubElement(icon, 'IconStyle', _ole_attrs)
        elif rep_val == Representation.THEME_LINE.value:
            theme = ET.SubElement(entity_el, 'Theme')
            theme_style_attrs: Dict[str, str] = {
                'Strength': str(style.get('strength', 'Default')),
            }
            if entity_type:
                theme_style_attrs['Type'] = entity_type
            if et_id:
                theme_style_attrs['EntityTypeReference'] = et_id
            if 'line_width' in style:
                theme_style_attrs['LineWidth'] = str(int(style['line_width']))
            if style.get('enlargement'):
                theme_style_attrs['Enlargement'] = style['enlargement']
            if style.get('shade_color'):
                theme_style_attrs['IconShadingColour'] = str(int(style['shade_color']))
            if style.get('line_color') is not None:
                theme_style_attrs['LineColour'] = str(int(style['line_color']))
            if style.get('type_icon_name'):
                theme_style_attrs['OverrideTypeIcon'] = 'true'
                theme_style_attrs['TypeIconName'] = style['type_icon_name']
            theme_style = ET.SubElement(theme, 'ThemeStyle', theme_style_attrs)
            _maybe_frame_style(theme_style, style)
        else:
            # Fallback: Icon
            icon = ET.SubElement(entity_el, 'Icon', _icon_text_attrs(style))
            _fb_attrs: Dict[str, str] = {
                'Type': entity_type,
            }
            if et_id:
                _fb_attrs['EntityTypeReference'] = et_id
            if style.get('enlargement'):
                _fb_attrs['Enlargement'] = style['enlargement']
            if style.get('shade_color'):
                _fb_attrs['IconShadingColour'] = str(int(style['shade_color']))
            icon_style = ET.SubElement(icon, 'IconStyle', _fb_attrs)
            _maybe_frame_style(icon_style, style)

    def _add_attributes(
        self,
        ci_el: ET.Element,
        attrs: List[_AttrTuple],
    ) -> None:
        att_coll = ET.SubElement(ci_el, 'AttributeCollection')
        for attr in attrs:
            if attr.value is None:
                continue
            ac_id = self._att_classes[attr.class_name][0]
            ET.SubElement(att_coll, 'Attribute', {
                'AttributeClass': attr.class_name,
                'AttributeClassReference': ac_id,
                'Value': str(attr.value),
            })

    @staticmethod
    def _norm_bool(val: Any) -> Optional[str]:
        """Normalise a bool/string font flag to 'true'/'false', or None if not set."""
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        if isinstance(val, bool):
            return 'true' if val else 'false'
        s = str(val).strip().lower()
        if s in ('true', 'false'):
            return s
        return None

    @staticmethod
    def _norm_color(val: Any) -> Optional[str]:
        """Normalise a color value (int COLORREF or color string) to its string form,
        or None if not set."""
        if val is None:
            return None
        if isinstance(val, float) and math.isnan(val):
            return None
        # Unwrap Color enum (str-Enum) before further checks
        if hasattr(val, 'value'):
            val = val.value
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return str(int(val))
        s = str(val).strip()
        if not s:
            return None
        return str(color_to_colorref(s))

    _SUMMARY_FIELD_MAP = {
        'title': 'SummaryFieldTitle',
        'subject': 'SummaryFieldSubject',
        'keywords': 'SummaryFieldKeywords',
        'category': 'SummaryFieldCategory',
        'comments': 'SummaryFieldComments',
        'author': 'SummaryFieldAuthor',
        'template': 'SummaryFieldTemplate',
    }
    _ORIGIN_ATTR_MAP = {
        'created':    'CreatedDate',
        'edit_time':  'EditTime',
        'last_print': 'LastPrintDate',
        'last_save':  'LastSaveDate',
        'revision':   'RevisionNumber',
    }

    def _emit_summary(self, parent: ET.Element, cfg: Dict[str, Any]) -> None:
        """Emit a <Summary> element with FieldCollection, CustomPropertyCollection, and Origin."""
        summary_el = ET.SubElement(parent, 'Summary')

        # FieldCollection
        fields = cfg.get('fields', {})
        if fields:
            fc = ET.SubElement(summary_el, 'FieldCollection')
            for key, value in fields.items():
                xml_type = self._SUMMARY_FIELD_MAP.get(key)
                if xml_type and value:
                    ET.SubElement(fc, 'Field', {'Type': xml_type, 'Field': str(value)})

        # CustomPropertyCollection
        cps = cfg.get('custom_properties', [])
        if cps:
            cpc = ET.SubElement(summary_el, 'CustomPropertyCollection')
            for cp in cps:
                # Duck-type check for CustomProperty dataclass (vs dict), not enum resolution.
                if hasattr(cp, 'name') and hasattr(cp, 'value'):
                    cp_name = str(cp.name)
                    cp_value = str(cp.value)
                else:
                    cp_name = str(cp.get('name', ''))
                    cp_value = str(cp.get('value', ''))
                ET.SubElement(cpc, 'CustomProperty', {
                    'Name': cp_name,
                    'Type': 'String',
                    'Value': cp_value,
                })

        # Origin — auto-defaults merged with user values.  Date / datetime
        # values are formatted explicitly so YAML-parsed datetime literals
        # don't leak Python's space-separated str() form into ANB's expected
        # ISO 8601 ``T`` form.
        from datetime import date as _date
        def _fmt_origin(val: Any) -> str:
            if isinstance(val, datetime):
                return val.strftime('%Y-%m-%dT%H:%M:%S')
            if isinstance(val, _date):
                return val.strftime('%Y-%m-%d')
            return str(val)
        origin = cfg.get('origin', {})
        now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        defaults = {'created': now, 'edit_time': '0', 'revision': '1'}
        merged = {**defaults, **{k: _fmt_origin(v) for k, v in origin.items()}}
        origin_attrs: Dict[str, str] = {}
        for key, xml_attr in self._ORIGIN_ATTR_MAP.items():
            if key in merged:
                origin_attrs[xml_attr] = merged[key]
        ET.SubElement(summary_el, 'Origin', origin_attrs)

    def _emit_palette(self, parent: ET.Element, pal: Dict[str, Any]) -> None:
        """Emit a single <Palette> element with its entry collections."""
        pal_attrs: Dict[str, str] = {'Name': pal.get('name', 'anxwritter')}
        if pal.get('locked'):
            pal_attrs['Locked'] = 'true'
        pal_el = ET.SubElement(parent, 'Palette', pal_attrs)

        # AttributeClassEntryCollection (class definitions, no values)
        ac_names = pal.get('attribute_classes', [])
        if ac_names:
            acec = ET.SubElement(pal_el, 'AttributeClassEntryCollection')
            for ac_name in ac_names:
                ac_info = self._att_classes.get(ac_name)
                if ac_info:
                    ET.SubElement(acec, 'AttributeClassEntry', {
                        'AttributeClass': ac_name,
                        'AttributeClassReference': ac_info[0],
                    })

        # AttributeEntryCollection (entries with pre-filled values)
        ae_entries = pal.get('attribute_entries', [])
        if ae_entries:
            aec = ET.SubElement(pal_el, 'AttributeEntryCollection')
            for ae in ae_entries:
                ac_info = self._att_classes.get(ae.get('name', ''))
                if ac_info:
                    attrs: Dict[str, str] = {
                        'AttributeClass': ae['name'],
                        'AttributeClassReference': ac_info[0],
                    }
                    if ae.get('value') is not None:
                        attrs['Value'] = str(ae['value'])
                    ET.SubElement(aec, 'AttributeClassEntry', attrs)

        # EntityTypeEntryCollection
        et_names = pal.get('entity_types', [])
        if et_names:
            etec = ET.SubElement(pal_el, 'EntityTypeEntryCollection')
            for et_name in et_names:
                et_id = self._entity_types.get(et_name)
                if et_id:
                    ET.SubElement(etec, 'EntityTypeEntry', {
                        'Entity': et_name,
                        'EntityTypeReference': et_id,
                    })

        # LinkTypeEntryCollection
        lt_names = pal.get('link_types', [])
        if lt_names:
            ltec = ET.SubElement(pal_el, 'LinkTypeEntryCollection')
            for lt_name in lt_names:
                lt_id = self._link_types.get(lt_name)
                if lt_id:
                    ET.SubElement(ltec, 'LinkTypeEntry', {
                        'LinkType': lt_name,
                        'LinkTypeReference': lt_id,
                    })

    def _add_ci_style(
        self,
        ci_el: ET.Element,
        *,
        background: Any = None,
        show_datetime_description: Any = None,
        sub_text_width: Any = None,
        use_sub_text_width: Any = None,
        label_color: Any = None,
        label_bg_color: Any = None,
        label_face: Any = None,
        label_size: Any = None,
        label_bold: Any = None,
        label_italic: Any = None,
        label_strikeout: Any = None,
        label_underline: Any = None,
        subitem_description: Any = None,
        subitem_grades: Any = None,
        subitem_label: Any = None,
        subitem_date: Any = None,
        subitem_source_ref: Any = None,
        subitem_source_type: Any = None,
        subitem_pin: Any = None,
        datetime_format: Any = None,
    ) -> None:
        # ── CIStyle attributes — only include what is explicitly set ─────
        # Background: makes the entity act as a non-selectable background image.
        # ShowDateTimeDescription: when true, displays the formatted date/time
        #   description string instead of the raw date/time values.
        # SubTextWidth / UseSubTextWidth: purpose not fully confirmed.
        ci_style_attrs: Dict[str, str] = {}
        if datetime_format is not None and datetime_format != '':
            # ANB 9 resolves the DateTimeFormat attribute against the
            # DateTimeFormatCollection by name. Inline format strings are NOT
            # supported — ANB 9 rejects them with "NULL argument passed to
            # SetDateTimeFormat". Only emit when the name is registered.
            dtf_str = str(datetime_format)
            if dtf_str in self._datetime_formats:
                ci_style_attrs['DateTimeFormat'] = dtf_str
        if background is not None:
            ci_style_attrs['Background'] = 'true' if background else 'false'
        if show_datetime_description is not None:
            ci_style_attrs['ShowDateTimeDescription'] = 'true' if show_datetime_description else 'false'
        if sub_text_width is not None:
            ci_style_attrs['SubTextWidth'] = str(float(sub_text_width))
        if use_sub_text_width is not None:
            ci_style_attrs['UseSubTextWidth'] = 'true' if use_sub_text_width else 'false'

        # ── Font — only emit when at least one font param is explicitly set
        font_attrs: Dict[str, str] = {}
        _font_candidates = {
            'FontColour':  self._norm_color(label_color),
            'BackColour':  self._norm_color(label_bg_color),
            'FaceName':    str(label_face).strip() if label_face is not None and not (isinstance(label_face, float) and math.isnan(label_face)) else None,
            'PointSize':   str(int(float(label_size))) if label_size is not None and not (isinstance(label_size, float) and math.isnan(label_size)) else None,
            'Bold':        self._norm_bool(label_bold),
            'Italic':      self._norm_bool(label_italic),
            'Strikeout':   self._norm_bool(label_strikeout),
            'Underline':   self._norm_bool(label_underline),
        }
        for key, val in _font_candidates.items():
            if val is not None:
                font_attrs[key] = val

        # ── SubItem visibility — only emit when at least one is explicitly set
        _sub_params = {
            'SubItemDescription':    subitem_description,
            'SubItemGrades':         subitem_grades,
            'SubItemLabel':          subitem_label,
            'SubItemPin':            subitem_pin,
            'SubItemSourceReference':subitem_source_ref,
            'SubItemSourceType':     subitem_source_type,
            'SubItemDateTime':       subitem_date,
        }
        _sub_explicit = {k: v for k, v in _sub_params.items()
                         if v is not None and not (isinstance(v, float) and math.isnan(v))}

        # ── Only emit <CIStyle> if there is anything to put in it ────────
        if not ci_style_attrs and not font_attrs and not _sub_explicit:
            return

        style = ET.SubElement(ci_el, 'CIStyle', ci_style_attrs)

        if font_attrs:
            ET.SubElement(style, 'Font', font_attrs)

        if _sub_explicit:
            _sub_defaults = {
                'SubItemDescription':    False,
                'SubItemGrades':         False,
                'SubItemLabel':          True,
                'SubItemPin':            False,
                'SubItemSourceReference':False,
                'SubItemSourceType':     False,
                'SubItemDateTime':       False,
            }
            sub_coll = ET.SubElement(style, 'SubItemCollection')
            for sub_type, default_vis in _sub_defaults.items():
                raw = _sub_params[sub_type]
                visible = (raw if raw is not None and not (isinstance(raw, float) and math.isnan(raw)) else default_vis)
                ET.SubElement(sub_coll, 'SubItem', {'Type': sub_type, 'Visible': 'true' if visible else 'false'})

    # ── LibraryCatalogue emission ─────────────────────────────────────────────

    def _build_catalogue(self, root: ET.Element, semantic_config: Dict[str, Any]) -> None:
        """Build and insert ``<lcx:LibraryCatalogue>`` after ``<ApplicationVersion>``."""
        from .semantic import (
            LCX_NS, LCX_VERSION, ROOT_NAMES, ROOTS,
            TYPE_ROOTS, PROPERTY_ROOTS,
            ancestor_chain, generate_guid,
        )

        def _lcx(tag: str) -> str:
            return f'{{{LCX_NS}}}{tag}'

        custom_entities = semantic_config.get('custom_entities', {})
        custom_links = semantic_config.get('custom_links', {})
        custom_properties = semantic_config.get('custom_properties', {})
        ref_type_guids = semantic_config.get('referenced_type_guids', set())
        ref_prop_guids = semantic_config.get('referenced_property_guids', set())

        # Build unified lookup: roots + custom types (for ancestor chain resolution)
        # Types (entity + link share lcx:Type)
        type_lookup: Dict[str, Dict[str, Any]] = {}
        guid_to_name: Dict[str, str] = {}

        # Add type-tree roots (entity / link) if not already present.
        for root_guid, root_name in ROOT_NAMES.items():
            if root_name not in type_lookup and root_guid in TYPE_ROOTS:
                type_lookup[root_name] = {'guid': root_guid, 'parent_guid': None, 'abstract': True}
                guid_to_name[root_guid] = root_name

        # Inject custom entity types into the lookup (resolve kind_of to parent GUID)
        for name, entry in custom_entities.items():
            kind_of_name = entry['kind_of']
            parent = type_lookup.get(kind_of_name)
            parent_guid = parent['guid'] if parent else None
            type_lookup[name] = {
                'guid': entry['guid'], 'parent_guid': parent_guid, 'abstract': entry.get('abstract', False),
            }
            guid_to_name[entry['guid']] = name

        # Inject custom link types
        for name, entry in custom_links.items():
            kind_of_name = entry['kind_of']
            parent = type_lookup.get(kind_of_name)
            parent_guid = parent['guid'] if parent else None
            type_lookup[name] = {
                'guid': entry['guid'], 'parent_guid': parent_guid, 'abstract': entry.get('abstract', False),
            }
            guid_to_name[entry['guid']] = name

        # Property lookup
        prop_lookup: Dict[str, Dict[str, Any]] = {}
        # Add property-tree roots (text / number / datetime / flag).
        for root_guid, root_name in ROOT_NAMES.items():
            if root_name not in prop_lookup and root_guid in PROPERTY_ROOTS:
                prop_lookup[root_name] = {'guid': root_guid, 'parent_guid': None, 'abstract': True}
                guid_to_name[root_guid] = root_name

        # Inject custom properties
        for name, entry in custom_properties.items():
            bp_name = entry['base_property']
            parent = prop_lookup.get(bp_name)
            parent_guid = parent['guid'] if parent else None
            prop_lookup[name] = {
                'guid': entry['guid'], 'parent_guid': parent_guid, 'abstract': entry.get('abstract', False),
            }
            guid_to_name[entry['guid']] = name

        # Collect all type names that need catalogue entries (referenced + ancestors)
        needed_type_names: List[str] = []
        seen_type_names: set = set()
        for guid in ref_type_guids:
            name = guid_to_name.get(guid)
            if not name or name in seen_type_names:
                continue
            try:
                chain = ancestor_chain(name, type_lookup, guid_to_name)
            except ValueError:
                continue
            for n in chain:
                if n not in seen_type_names:
                    seen_type_names.add(n)
                    needed_type_names.append(n)

        # Also add custom entity/link types (they might not be referenced via EntityType/LinkType)
        for name in list(custom_entities) + list(custom_links):
            if name not in seen_type_names:
                try:
                    chain = ancestor_chain(name, type_lookup, guid_to_name)
                except ValueError:
                    continue
                for n in chain:
                    if n not in seen_type_names:
                        seen_type_names.add(n)
                        needed_type_names.append(n)

        # Collect property names
        needed_prop_names: List[str] = []
        seen_prop_names: set = set()
        for guid in ref_prop_guids:
            name = guid_to_name.get(guid)
            if not name or name in seen_prop_names:
                continue
            try:
                chain = ancestor_chain(name, prop_lookup, guid_to_name)
            except ValueError:
                continue
            for n in chain:
                if n not in seen_prop_names:
                    seen_prop_names.add(n)
                    needed_prop_names.append(n)

        for name in custom_properties:
            if name not in seen_prop_names:
                try:
                    chain = ancestor_chain(name, prop_lookup, guid_to_name)
                except ValueError:
                    continue
                for n in chain:
                    if n not in seen_prop_names:
                        seen_prop_names.add(n)
                        needed_prop_names.append(n)

        # Nothing to emit?
        if not needed_type_names and not needed_prop_names:
            return

        # Build the XML element
        lib = ET.Element(_lcx('LibraryCatalogue'), LCX_VERSION)

        # Emit lcx:Type entries (topological order — ancestors first)
        for name in needed_type_names:
            entry = type_lookup.get(name)
            if not entry:
                continue
            attrs: Dict[str, str] = {'tGUID': entry['guid']}
            if entry.get('parent_guid'):
                attrs['kindOf'] = entry['parent_guid']
            if entry.get('abstract'):
                attrs['abstract'] = 'true'
            t_el = ET.SubElement(lib, _lcx('Type'), attrs)
            ET.SubElement(t_el, 'TypeName').text = name

            # Custom type metadata (Documentation)
            custom = custom_entities.get(name) or custom_links.get(name)
            if custom:
                synonyms = custom.get('synonyms') or []
                description = custom.get('description')
                if synonyms or description:
                    doc = ET.SubElement(t_el, 'Documentation')
                    for syn in synonyms:
                        ET.SubElement(doc, _lcx('Synonym')).text = syn
                    # Description is mandatory inside Documentation
                    ET.SubElement(doc, 'Description').text = description or ''

        # Emit lcx:Property entries
        for name in needed_prop_names:
            entry = prop_lookup.get(name)
            if not entry:
                continue
            attrs = {'pGUID': entry['guid']}
            if entry.get('parent_guid'):
                attrs['baseProperty'] = entry['parent_guid']
            if entry.get('abstract'):
                attrs['abstract'] = 'true'
            p_el = ET.SubElement(lib, _lcx('Property'), attrs)
            ET.SubElement(p_el, 'PropertyName').text = name

            custom = custom_properties.get(name)
            if custom:
                synonyms = custom.get('synonyms') or []
                description = custom.get('description')
                if synonyms or description:
                    doc = ET.SubElement(p_el, 'Documentation')
                    for syn in synonyms:
                        ET.SubElement(doc, _lcx('Synonym')).text = syn
                    # Description is mandatory inside Documentation
                    ET.SubElement(doc, 'Description').text = description or ''

        # Insert after ApplicationVersion (position 1 in Chart children)
        for i, child in enumerate(root):
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'ApplicationVersion':
                root.insert(i + 1, lib)
                break
        else:
            root.insert(0, lib)

        # Add xmlns:lcx declaration on root Chart element
        root.set(f'xmlns:lcx', LCX_NS)

    # ── Full document assembly ────────────────────────────────────────────────

    def build(
        self,
        settings: Optional[Any] = None,
        att_class_config: Optional[Dict[str, Dict[str, Any]]] = None,
        strength_config: Optional[Dict[str, str]] = None,
        gc1: Optional[List[str]] = None,
        gc2: Optional[List[str]] = None,
        gc3: Optional[List[str]] = None,
        source_types: Optional[List[str]] = None,
        legend_items: Optional[List[Dict[str, Any]]] = None,
        palettes: Optional[List[Dict[str, Any]]] = None,
        datetime_format_config: Optional[List[Dict[str, str]]] = None,
        summary_config: Optional[Dict[str, Any]] = None,
        semantic_config: Optional[Dict[str, Any]] = None,
        layout_center: tuple = (0, 0),
    ) -> str:
        """Assemble the complete ANX XML and return a pretty-printed string.

        ``settings`` is the ``Settings`` dataclass from chart.py (or None for
        a fresh default).
        """
        self._build_timer = PhaseTimer("ANXBuilder.build")
        _timer = self._build_timer

        from .models import Settings
        s = settings if settings is not None else Settings()
        acc_cfg = att_class_config or {}

        # Resolve chart background once for downstream callers (e.g. Label borders)
        bg_val = _resolve_path(s, 'chart.bg_color')
        if bg_val is None:
            self._chart_bg_color: int = 16777215
        elif isinstance(bg_val, int):
            self._chart_bg_color = bg_val
        else:
            # color_to_colorref unwraps Color enum and accepts strings
            self._chart_bg_color = color_to_colorref(bg_val)

        with _timer.phase("Register strengths"):
            # Register strengths from chart.sc before building XML
            for sc_name, sc_dot in (strength_config or {}).items():
                self.register_strength(sc_name, sc_dot)

        with _timer.phase("Register datetime formats"):
            for dtf in (datetime_format_config or []):
                self.register_datetime_format(dtf['name'], dtf.get('format', ''))

        with _timer.phase("Apply layout"):
            # Apply auto-layout to all registered entities
            self._apply_layout(
                _resolve_path(s, 'extra_cfg.arrange') or 'circle',
                center=layout_center,
            )

        with _timer.phase("Root element"):
            chart_attrs: Dict[str, str] = {}
            for path, xml_attr, typ in _CHART_ATTR_MAP:
                val = _resolve_path(s, path)
                if val is None:
                    continue
                # Resolve short enum aliases for str-type settings
                if typ == 'str' and path in _SETTINGS_ENUM_MAPS:
                    val = _resolve_enum(val, _SETTINGS_ENUM_MAPS[path])
                chart_attrs[xml_attr] = _fmt_chart_attr(val, typ)
            root = ET.Element('Chart', chart_attrs)

        ET.SubElement(root, 'ApplicationVersion', {
            'Major': '9', 'Minor': '0', 'Point': '0', 'Build': '0',
            })

        # ── LibraryCatalogue (semantic types) ────────────────────────────
        with _timer.phase("LibraryCatalogue"):
            if semantic_config:
                self._build_catalogue(root, semantic_config)

        with _timer.phase("StrengthCollection"):
            # StrengthCollection
            sc = ET.SubElement(root, 'StrengthCollection')
            for name, s_id in self._strengths.items():
                ET.SubElement(sc, 'Strength', {
                    'Id': s_id, 'Name': name,
                    'DotStyle': _resolve_enum(self._strength_dot_styles.get(name, 'DotStyleSolid'), _DOT_MAP),
                })

        with _timer.phase("Grade/Source collections"):
            # GradeOne / GradeTwo / GradeThree / SourceHints collections
            for tag, names in (('GradeOne', gc1 or []), ('GradeTwo', gc2 or []),
                               ('GradeThree', gc3 or []), ('SourceHints', source_types or [])):
                if names:
                    gc_el = ET.SubElement(root, tag)
                    sc_el = ET.SubElement(gc_el, 'StringCollection')
                    for name in names:
                        ET.SubElement(sc_el, 'String', {'Id': self._next_id(), 'Text': name})

        _t0_acc = _time.perf_counter()

        # Ensure every config-declared AttributeClass is registered and emitted,
        # even when no entity/link data references it. Explicit declarations are
        # first-class artefacts — users register them to reference later in ANB.
        # Type conflicts between config and data are caught by validate() before
        # this method is ever called, so the inferred type is trusted here.
        for ac_name, ac_row in acc_cfg.items():
            if ac_name in self._att_classes:
                continue
            declared = ac_row.get('type')
            if declared is None:
                continue  # validate() already flagged this as missing_required
            att_type = _ATT_TYPE.get(_enum_val(declared).lower(), 'AttText')
            self._att_classes[ac_name] = (self._next_id(), att_type)

        def _ac_bool(val: Any, default: str) -> str:
            """Convert a chart.ac cell value to 'true'/'false', falling back to default."""
            if val is None or (isinstance(val, float) and math.isnan(val)):
                return default
            return 'true' if bool(val) else 'false'

        # AttributeClassCollection (user-defined only)
        if self._att_classes:
            acc = ET.SubElement(root, 'AttributeClassCollection')
            for name, (ac_id, att_type) in self._att_classes.items():
                cfg_row = acc_cfg.get(name, {})
                # Mandatory attributes
                ac_attrs: Dict[str, str] = {
                    'Id':   ac_id,
                    'Name': name,
                    'Type': att_type,
                }
                # Always emit — default to true so attributes are editable in ANB
                ac_attrs['IsUser'] = _ac_bool(cfg_row.get('is_user'), 'true')
                ac_attrs['UserCanAdd'] = _ac_bool(cfg_row.get('user_can_add'), 'true')
                ac_attrs['UserCanRemove'] = _ac_bool(cfg_row.get('user_can_remove'), 'true')
                # Optional attributes — only emitted when explicitly set
                if name in self._att_class_icons:
                    ac_attrs['IconFile'] = self._att_class_icons[name]
                elif 'icon_file' in cfg_row:
                    ac_attrs['IconFile'] = str(cfg_row['icon_file'])
                if 'prefix' in cfg_row:
                    prefix = str(cfg_row['prefix'])
                    ac_attrs['Prefix'] = prefix
                    ac_attrs['ShowPrefix'] = 'true' if prefix else 'false'
                if 'suffix' in cfg_row:
                    suffix = str(cfg_row['suffix'])
                    ac_attrs['Suffix'] = suffix
                    ac_attrs['ShowSuffix'] = 'true' if suffix else 'false'
                if 'show_class_name' in cfg_row:
                    ac_attrs['ShowClassName'] = _ac_bool(cfg_row.get('show_class_name'), 'false')
                if 'show_symbol' in cfg_row:
                    ac_attrs['ShowSymbol'] = _ac_bool(cfg_row.get('show_symbol'), 'true')
                if 'show_value' in cfg_row:
                    ac_attrs['ShowValue'] = _ac_bool(cfg_row.get('show_value'), 'true')
                if 'show_date' in cfg_row:
                    ac_attrs['ShowDate'] = _ac_bool(cfg_row.get('show_date'), 'true' if att_type == 'AttTime' else 'false')
                if 'show_time' in cfg_row:
                    ac_attrs['ShowTime'] = _ac_bool(cfg_row.get('show_time'), 'true' if att_type == 'AttTime' else 'false')
                if 'show_seconds' in cfg_row:
                    ac_attrs['ShowSeconds'] = _ac_bool(cfg_row.get('show_seconds'), 'false')
                if 'decimal_places' in cfg_row:
                    ac_attrs['DecimalPlaces'] = str(int(cfg_row['decimal_places']))
                if 'visible' in cfg_row:
                    ac_attrs['Visible'] = _ac_bool(cfg_row.get('visible'), 'true')
                if 'show_if_set' in cfg_row:
                    ac_attrs['ShowIfSet'] = _ac_bool(cfg_row.get('show_if_set'), 'false')
                if 'merge_behaviour' in cfg_row:
                    v = cfg_row['merge_behaviour']
                    ac_attrs['MergeBehaviour'] = _resolve_enum(v, _MERGE_MAP)
                if 'paste_behaviour' in cfg_row:
                    v = cfg_row['paste_behaviour']
                    ac_attrs['PasteBehaviour'] = _resolve_enum(v, _MERGE_MAP)
                if 'semantic_type' in cfg_row:
                    ac_attrs['SemanticTypeGuid'] = str(cfg_row['semantic_type'])
                ac_el = ET.SubElement(acc, 'AttributeClass', ac_attrs)
                ac_font_ov = _font_overrides_from_dc(cfg_row.get('font'))
                if ac_font_ov:
                    self._font_el(ac_el, _FONT_DEFAULTS_AC, ac_font_ov)

        _timer.record("AttributeClassCollection", _time.perf_counter() - _t0_acc)

        with _timer.phase("Type collections"):
            # EntityTypeCollection
            if self._entity_types:
                etc = ET.SubElement(root, 'EntityTypeCollection')
                for name, et_id in self._entity_types.items():
                    meta = self._etype_meta.get(name, {})
                    et_attrs: Dict[str, str] = {'Id': et_id, 'Name': name}
                    if 'pref_rep' in meta:
                        et_attrs['PreferredRepresentation'] = meta['pref_rep']
                    if 'icon_file' in meta:
                        et_attrs['IconFile'] = meta['icon_file']
                    if 'color' in meta:
                        et_attrs['Colour'] = str(meta['color'])
                    if 'shade_color' in meta:
                        et_attrs['IconShadingColour'] = str(meta['shade_color'])
                    if 'semantic_type' in meta:
                        et_attrs['SemanticTypeGuid'] = meta['semantic_type']
                    ET.SubElement(etc, 'EntityType', et_attrs)

            # LinkTypeCollection
            if self._link_types:
                ltc = ET.SubElement(root, 'LinkTypeCollection')
                for name, lt_id in self._link_types.items():
                    lt_attrs: Dict[str, str] = {'Id': lt_id, 'Name': name}
                    lt_meta = self._ltype_meta.get(name, {})
                    if lt_meta.get('color') is not None:
                        lt_attrs['Colour'] = str(lt_meta['color'])
                    if lt_meta.get('semantic_type') is not None:
                        lt_attrs['SemanticTypeGuid'] = lt_meta['semantic_type']
                    ET.SubElement(ltc, 'LinkType', lt_attrs)

        with _timer.phase("DateTimeFormatCollection"):
            if self._datetime_formats:
                dtfc = ET.SubElement(root, 'DateTimeFormatCollection')
                for dtf_name, (dtf_id, dtf_fmt) in self._datetime_formats.items():
                    dtf_attrs: Dict[str, str] = {'Id': dtf_id, 'Name': dtf_name}
                    if dtf_fmt:
                        dtf_attrs['Format'] = dtf_fmt
                    ET.SubElement(dtfc, 'DateTimeFormat', dtf_attrs)

        with _timer.phase("ChartItems + positions"):
            # Chart-level Font — only emitted when user explicitly sets any settings.font.* field
            chart_font_ov = _font_overrides_from_dc(getattr(s, 'font', None))
            if chart_font_ov:
                self._font_el(root, _FONT_DEFAULTS_CHART, chart_font_ov)

            # Summary — emitted between Font and ChartItemCollection
            if summary_config:
                self._emit_summary(root, summary_config)

            # Emit resolved items with layout positions applied
            from .resolved import ResolvedEntity
            for item in self._resolved_items:
                if isinstance(item, ResolvedEntity):
                    pos = self._positions.get(item.identity, (0, 0))
                    item.x, item.y = pos
                    self.emit_entity(item)
                else:
                    self.emit_link(item)

            # ChartItemCollection
            cic = ET.SubElement(root, 'ChartItemCollection')
            for ci_el in self._chart_item_elements:
                cic.append(ci_el)

        with _timer.phase("Connections + palettes"):
            # ConnectionCollection — emit pre-built style_conn dict (no iteration over links)
            if self._has_conn_fields and self._style_conn:
                conn_coll = ET.SubElement(root, 'ConnectionCollection')
                for style, conn_id in self._style_conn.items():
                    conn_el = ET.SubElement(conn_coll, 'Connection', {'Id': conn_id})
                    cs_attrs: Dict[str, str] = {}
                    if style[0] is not None:
                        cs_attrs['Multiplicity'] = _resolve_enum(style[0], _MULT_MAP)
                    if style[1] is not None:
                        cs_attrs['FanOut'] = str(style[1])
                    if style[2] is not None:
                        cs_attrs['ThemeWiring'] = _resolve_enum(style[2], _THEME_WIRING_MAP)
                    ET.SubElement(conn_el, 'ConnectionStyle', cs_attrs)

            # PaletteCollection
            pal_coll = ET.SubElement(root, 'PaletteCollection')
            if palettes:
                # User-defined palettes
                for pal in palettes:
                    self._emit_palette(pal_coll, pal)
            else:
                # Auto-populate default palette with all registered types
                # Filter out attribute classes with is_user=false or user_can_add=false
                _auto_ac = [
                    name for name in self._att_classes
                    if _ac_bool(acc_cfg.get(name, {}).get('is_user'), 'true') == 'true'
                    and _ac_bool(acc_cfg.get(name, {}).get('user_can_add'), 'true') == 'true'
                ]
                auto_pal: Dict[str, Any] = {
                    'name': 'anxwritter',
                    'entity_types': list(self._entity_types.keys()),
                    'link_types': list(self._link_types.keys()),
                    'attribute_classes': _auto_ac,
                }
                self._emit_palette(pal_coll, auto_pal)

        # LegendDefinition — only emitted when there is content
        _t0_legend = _time.perf_counter()
        _LEGEND_PATH_MAP = [
            ('legend_cfg.arrange', 'Arrange',             'str'),
            ('legend_cfg.valign',  'VerticalAlignment',   'str'),
            ('legend_cfg.halign',  'HorizontalAlignment', 'str'),
            ('legend_cfg.x',       'X',                   'int'),
            ('legend_cfg.y',       'Y',                   'int'),
            ('legend_cfg.show',    'Shown',               'bool'),
        ]
        _LEGEND_ENUM_MAPS = {
            'legend_cfg.arrange': _LEGEND_ARRANGE_MAP,
            'legend_cfg.valign': _LEGEND_ALIGN_MAP,
            'legend_cfg.halign': _LEGEND_ALIGN_MAP,
        }
        leg_attrs: Dict[str, str] = {}
        for path, xml_attr, typ in _LEGEND_PATH_MAP:
            val = _resolve_path(s, path)
            if val is None:
                continue
            if typ == 'str' and path in _LEGEND_ENUM_MAPS:
                val = _resolve_enum(val, _LEGEND_ENUM_MAPS[path])
            leg_attrs[xml_attr] = _fmt_chart_attr(val, typ)
        legend_font_ov = _font_overrides_from_dc(_resolve_path(s, 'legend_cfg.font'))
        _has_legend = bool(leg_attrs or legend_font_ov or legend_items)

        if _has_legend:
            if 'Arrange' not in leg_attrs:
                leg_attrs['Arrange'] = 'LegendArrangementWide'
            leg = ET.SubElement(root, 'LegendDefinition', leg_attrs)
            if legend_font_ov:
                self._font_el(leg, _FONT_DEFAULTS_CHART, legend_font_ov)

            # Accept Title Case ('Font'), lowercase ('font'), and enum instances.
            _LI_TYPE_MAP = {
                'font':       'LegendItemTypeFont',
                'text':       'LegendItemTypeText',
                'icon':       'LegendItemTypeIcon',
                'attribute':  'LegendItemTypeAttribute',
                'line':       'LegendItemTypeLine',
                'link':       'LegendItemTypeLink',
                'timezone':   'LegendItemTypeTimeZone',
                'icon_frame': 'LegendItemTypeIconFrame',
            }
            for li_row in (legend_items or []):
                label_val = str(li_row.get('name', ''))
                raw = li_row.get('item_type', 'Font')
                raw_type = _enum_val(raw) if hasattr(raw, 'value') else str(raw)
                li_type = _LI_TYPE_MAP.get(raw_type.lower().replace(' ', '_'), 'LegendItemTypeFont')

                li_attrs: Dict[str, str] = {'Type': li_type, 'Label': label_val}

                if li_type in ('LegendItemTypeLine', 'LegendItemTypeLink'):
                    if 'color' in li_row:
                        li_attrs['Colour'] = str(int(li_row['color']))
                    if 'line_width' in li_row:
                        li_attrs['LineWidth'] = str(int(li_row['line_width']))
                    if 'dash_style' in li_row:
                        li_attrs['DashStyle'] = _resolve_enum(li_row['dash_style'], _DOT_MAP)
                    if li_type == 'LegendItemTypeLink' and 'arrows' in li_row:
                        li_attrs['Arrows'] = _resolve_enum(li_row['arrows'], _ARROW_MAP)

                elif li_type == 'LegendItemTypeIconFrame':
                    if 'color' in li_row:
                        li_attrs['Colour'] = str(int(li_row['color']))

                elif li_type in ('LegendItemTypeIcon', 'LegendItemTypeAttribute'):
                    if 'shade_color' in li_row:
                        li_attrs['IconShadingColour'] = str(int(li_row['shade_color']))
                    if li_row.get('image_name'):
                        li_attrs['ImageName'] = str(li_row['image_name'])

                li_el = ET.SubElement(leg, 'LegendItem', li_attrs)

                # Font/Text/TimeZone MUST have a <Font> child (ANB requires it).
                # Other types with font: emit only when user sets font fields.
                _FONT_REQUIRED_TYPES = (
                    'LegendItemTypeFont', 'LegendItemTypeText', 'LegendItemTypeTimeZone',
                )
                if li_type not in ('LegendItemTypeLine', 'LegendItemTypeLink'):
                    li_font_ov = _font_overrides_from_dc(li_row.get('font'))
                    if li_font_ov:
                        self._font_el(li_el, _FONT_DEFAULTS_CHART, li_font_ov)
                    elif li_type in _FONT_REQUIRED_TYPES:
                        # Empty <Font/> — ANB requires the tag but no attrs needed
                        ET.SubElement(li_el, 'Font')

        _timer.record("LegendDefinition", _time.perf_counter() - _t0_legend)

        with _timer.phase("XML serialization"):
            result = self._pretty_print(root)
        return result

    # ── Layout ───────────────────────────────────────────────────────────────

    def _apply_layout(self, mode: str, center: tuple = (0, 0)) -> None:
        """Calculate (X, Y) positions for all registered entities.

        Entities that already have a position in ``_positions`` (set manually
        via ``chart.e`` x/y columns or geo_map) are skipped.

        Args:
            mode: Layout algorithm — ``'circle'``, ``'grid'``, or ``'random'``.
            center: ``(cx, cy)`` offset for the layout origin. Used by geo_map
                to place unmatched entities below the geo-positioned area.
        """
        cx, cy = center
        keys = list(self._entity_registry.keys())  # List[str] — identity strings
        auto_keys = [k for k in keys if k not in self._positions]
        n = len(auto_keys)
        if n == 0:
            return

        if mode == 'grid':
            cols = math.ceil(math.sqrt(n))
            spacing = 200
            for i, key in enumerate(auto_keys):
                row_i, col_i = divmod(i, cols)
                x = cx + col_i * spacing - (cols - 1) * spacing // 2
                y = cy + row_i * spacing - ((n // cols) - 1) * spacing // 2
                self._positions[key] = (x, y)

        elif mode == 'circle':
            radius = max(150, n * 35)
            for i, key in enumerate(auto_keys):
                angle = 2 * math.pi * i / n
                x = cx + int(radius * math.cos(angle))
                y = cy + int(radius * math.sin(angle))
                self._positions[key] = (x, y)

        else:  # random / default
            import random
            rng = random.Random(42)
            for key in auto_keys:
                x = cx + rng.randint(-400, 400)
                y = cy + rng.randint(-400, 400)
                self._positions[key] = (x, y)

    # ── Helper utilities ──────────────────────────────────────────────────────

    @staticmethod
    @lru_cache(maxsize=1024)
    def _format_datetime(
        date_val: Any, time_val: Any
    ) -> Tuple[bool, bool, Optional[str]]:
        """Return ``(date_set, time_set, iso_datetime_str)``.

        Accepts strings in any of the formats the validator accepts, plus
        Python ``datetime.date`` / ``datetime.datetime`` for *date_val* and
        ``datetime.time`` / ``datetime.datetime`` for *time_val*.  Typed
        inputs are normalised to canonical strings up front so the rest of
        the function (originally string-only) needs no further changes.
        """
        if date_val is None:
            return False, False, None

        from datetime import date as _date_cls, time as _time_cls

        # ── Normalise typed inputs to canonical strings ──────────────────
        if isinstance(date_val, datetime):
            # If the user packed a time into the datetime and didn't pass
            # one separately, lift it across so the time_set branch fires.
            if time_val is None and (date_val.hour or date_val.minute
                                      or date_val.second or date_val.microsecond):
                time_val = date_val.time()
            date_str: str = date_val.strftime('%Y-%m-%d')
        elif isinstance(date_val, _date_cls):
            date_str = date_val.strftime('%Y-%m-%d')
        else:
            date_str = date_val

        if time_val is None:
            time_str: Optional[str] = None
        elif isinstance(time_val, datetime):
            time_str = time_val.strftime('%H:%M:%S')
        elif isinstance(time_val, _time_cls):
            time_str = time_val.strftime('%H:%M:%S')
        else:
            time_str = time_val

        # Fast path: YYYY-MM-DD (the canonical API format)
        date_part: Optional[str] = None
        time_part: str = '00:00:00.000'
        time_set = False

        raw_date = date_str.split('T')[0].split(' ')[0]
        if len(raw_date) == 10 and raw_date[4] == '-' and raw_date[7] == '-':
            date_part = raw_date  # already canonical, no strptime needed
        else:
            for fmt in ('%d/%m/%Y', '%Y%m%d'):
                try:
                    date_part = datetime.strptime(raw_date, fmt).strftime('%Y-%m-%d')
                    break
                except ValueError:
                    continue
            if date_part is None:
                date_part = raw_date  # use as-is if all formats fail

        if time_str:
            # Fast path: HH:MM:SS (the canonical API format)
            if len(time_str) == 8 and time_str[2] == ':' and time_str[5] == ':':
                time_part = time_str + '.000'
                time_set = True
            else:
                for fmt in ('%H:%M:%S.%f', '%H:%M', '%I:%M %p'):
                    try:
                        time_part = datetime.strptime(time_str, fmt).strftime('%H:%M:%S.000')
                        time_set = True
                        break
                    except ValueError:
                        continue
        elif 'T' in date_str:
            rest = date_str.split('T', 1)[1]
            time_part = rest[:8] + '.000' if len(rest) >= 8 else rest + '.000'
            time_set = True

        return True, time_set, f'{date_part}T{time_part}'

    # ── Pretty print ─────────────────────────────────────────────────────────

    @staticmethod
    def _pretty_print(root: ET.Element) -> str:
        return _fast_serialize(root)


# ── Fast XML serializer ──────────────────────────────────────────────────────
# Replaces ET.indent() + ET.tostring() with a single-pass tree walk that
# builds the output string directly.  ~2x faster than stdlib for large trees
# because it avoids the intermediate bytes→codec→TextIOWrapper pipeline.

# Reverse map: namespace URI → prefix (populated from ET._namespace_map)
_NS_MAP: Dict[str, str] = {}

_TAG_CACHE: Dict[str, str] = {}

def _init_ns_map() -> None:
    """Build URI→prefix map from ET's registered namespaces."""
    # ET._namespace_map stores uri→prefix (set by register_namespace)
    for uri, prefix in ET._namespace_map.items():
        _NS_MAP[uri] = prefix
    _TAG_CACHE.clear()  # namespace map changed — invalidate resolved tag cache

_ESC_TABLE = str.maketrans({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
})

# Pre-built indent strings for depths 0–19 (avoids '  ' * depth on every _walk call)
_INDENT = tuple('  ' * i for i in range(20))

def _esc(s: str) -> str:
    return s.translate(_ESC_TABLE)

def _resolve_tag(tag: str) -> str:
    """Convert {uri}local to prefix:local using registered namespaces."""
    resolved = _TAG_CACHE.get(tag)
    if resolved is not None:
        return resolved
    if tag[0] == '{':
        uri, local = tag[1:].split('}', 1)
        prefix = _NS_MAP.get(uri)
        resolved = f'{prefix}:{local}' if prefix else local
    else:
        resolved = tag
    _TAG_CACHE[tag] = resolved
    return resolved

def _fast_serialize(root: ET.Element) -> str:
    """Serialize an ElementTree to a pretty-printed UTF-16 XML string."""
    _init_ns_map()
    parts: list[str] = []
    from anxwritter import __version__, __repo_url__
    parts.append('<?xml version=\'1.0\' encoding=\'utf-16\'?>\n')
    comment = f'Built with anxwritter {__version__}'
    if __repo_url__:
        comment += f' \u2014 {__repo_url__}'
    parts.append(f'<!-- {comment} -->\n')
    _walk(root, parts, 0)
    return ''.join(parts)

def _walk(el: ET.Element, parts: list[str], depth: int) -> None:
    indent = _INDENT[depth] if depth < 20 else '  ' * depth
    tag = _resolve_tag(el.tag)

    # Opening tag — build as a single string to minimise append calls
    if el.attrib:
        attrs = ''.join(
            f' {_resolve_tag(k) if "{" in k else k}="{_esc(str(v))}"'
            for k, v in el.attrib.items()
        )
        open_tag = f'{indent}<{tag}{attrs}'
    else:
        open_tag = f'{indent}<{tag}'

    has_children = len(el) > 0
    text = el.text

    if not has_children and not text:
        parts.append(f'{open_tag}/>\n')
        return

    if text:
        if has_children:
            # Mixed content — rare in ANX
            parts.append(f'{open_tag}>\n{_INDENT[depth + 1] if depth + 1 < 20 else "  " * (depth + 1)}{text.translate(_ESC_TABLE)}\n')
        else:
            # Text-only element — inline
            parts.append(f'{open_tag}>{text.translate(_ESC_TABLE)}</{tag}>\n')
            return
    else:
        parts.append(f'{open_tag}>\n')

    for child in el:
        _walk(child, parts, depth + 1)

    parts.append(f'{indent}</{tag}>\n')
