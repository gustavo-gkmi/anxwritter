"""
Typed dataclasses for anxwritter's public API.
"""
from __future__ import annotations
import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List, Type, Union, get_args, get_origin, get_type_hints

from .enums import AttributeType, MergeBehaviour, DotStyle, Multiplicity, ThemeWiring, Representation, LegendItemType, Color


# ── Settings group helpers ───────────────────────────────────────────────────


def _get_inner_type(ftype: Any) -> type:
    """Extract the inner type from Optional[X] or similar generic types."""
    origin = get_origin(ftype)
    if origin is Union:
        # Optional[X] is Union[X, None] — return the first non-None type
        args = get_args(ftype)
        for arg in args:
            if arg is not type(None):
                return arg
    return ftype


def _build_group(cls: Type, raw: dict) -> Any:
    """Build a dataclass from a dict, recursing on nested dataclass fields.

    Used by Settings.from_dict() to convert nested dicts into dataclass instances.
    Raises TypeError for unknown fields (no silent drops).
    Also handles List[SomeDataclass] fields — each dict in the list is converted.
    """
    if not isinstance(raw, dict):
        raise TypeError(f"Expected dict for {cls.__name__}, got {type(raw).__name__}")

    # Check for unknown fields
    valid_fields = {fld.name for fld in dataclasses.fields(cls)}
    for key in raw:
        if key not in valid_fields:
            raise TypeError(
                f"Unknown {cls.__name__} field: {key!r}. "
                f"Valid fields: {', '.join(sorted(valid_fields))}."
            )

    # ``from __future__ import annotations`` stores fld.type as strings, so use
    # get_type_hints to resolve them to real types before inspecting.
    hints = get_type_hints(cls)

    kwargs: Dict[str, Any] = {}
    for fld in dataclasses.fields(cls):
        if fld.name not in raw:
            continue
        val = raw[fld.name]
        if val is None:
            continue

        # Check if field type is a dataclass
        ftype = _get_inner_type(hints.get(fld.name, fld.type))
        if isinstance(ftype, type) and dataclasses.is_dataclass(ftype) and isinstance(val, dict):
            kwargs[fld.name] = _build_group(ftype, val)
        elif isinstance(ftype, type) and dataclasses.is_dataclass(ftype) and isinstance(val, ftype):
            # Already the correct dataclass type
            kwargs[fld.name] = val
        elif get_origin(ftype) is list and isinstance(val, list):
            # Handle List[SomeDataclass] — convert each dict to the dataclass
            inner_args = get_args(ftype)
            if inner_args:
                inner_type = inner_args[0]
                if isinstance(inner_type, type) and dataclasses.is_dataclass(inner_type):
                    converted = []
                    for item in val:
                        if isinstance(item, dict):
                            converted.append(_build_group(inner_type, item))
                        elif isinstance(item, inner_type):
                            converted.append(item)
                        else:
                            converted.append(item)
                    kwargs[fld.name] = converted
                else:
                    kwargs[fld.name] = val
            else:
                kwargs[fld.name] = val
        else:
            kwargs[fld.name] = val

    return cls(**kwargs)


def _merge_group(existing: Any, raw: dict) -> None:
    """Merge a dict into an existing dataclass, recursing on nested dataclass fields.

    Used by Settings.merge_from_dict() to update existing instances in place.
    Only non-None values in raw are applied.
    Raises TypeError for unknown fields (no silent drops).
    """
    if not isinstance(raw, dict):
        raise TypeError(f"Expected dict, got {type(raw).__name__}")

    # Check for unknown fields
    cls = type(existing)
    valid_fields = {fld.name for fld in dataclasses.fields(existing)}
    for key in raw:
        if key not in valid_fields:
            raise TypeError(
                f"Unknown {cls.__name__} field: {key!r}. "
                f"Valid fields: {', '.join(sorted(valid_fields))}."
            )

    hints = get_type_hints(cls)

    for fld in dataclasses.fields(existing):
        if fld.name not in raw:
            continue
        val = raw[fld.name]
        if val is None:
            continue

        current = getattr(existing, fld.name)
        if dataclasses.is_dataclass(current) and isinstance(val, dict):
            _merge_group(current, val)
        elif current is None and isinstance(val, dict):
            # Field is currently None but incoming value is a dict — check if the
            # field type is a dataclass and build it from dict (e.g. geo_map).
            ftype = _get_inner_type(hints.get(fld.name, fld.type))
            if isinstance(ftype, type) and dataclasses.is_dataclass(ftype):
                setattr(existing, fld.name, _build_group(ftype, val))
            else:
                setattr(existing, fld.name, val)
        elif isinstance(val, list):
            # List[Dataclass] field — convert each dict item to the inner
            # dataclass type so e.g. summary.custom_properties items end up
            # as CustomProperty instances rather than raw dicts (mirrors the
            # behaviour of _build_group).  Replaces the list wholesale —
            # merge_from_dict's contract is "only fields present in raw
            # overwrite", and the user supplied an explicit list.
            ftype = _get_inner_type(hints.get(fld.name, fld.type))
            if get_origin(ftype) is list:
                inner_args = get_args(ftype)
                if inner_args and isinstance(inner_args[0], type) and dataclasses.is_dataclass(inner_args[0]):
                    inner_type = inner_args[0]
                    converted = [
                        _build_group(inner_type, item) if isinstance(item, dict)
                        else item
                        for item in val
                    ]
                    setattr(existing, fld.name, converted)
                else:
                    setattr(existing, fld.name, val)
            else:
                setattr(existing, fld.name, val)
        else:
            setattr(existing, fld.name, val)


# ── Font (shared shape used by chart default font, legend font, ...) ─────────

@dataclass
class Font:
    """Shared font shape used by chart default font, legend font, and (future)
    entity label / attribute class fonts. All fields default to ``None`` so the
    builder can apply 'only emit when explicitly set' semantics.
    """
    name: Optional[str] = None              # FaceName — typeface
    size: Optional[int] = None              # PointSize — size in points
    color: Optional[Union[int, str, Color]] = None # FontColour — text colour
    bg_color: Optional[Union[int, str, Color]] = None  # BackColour — text background
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    strikeout: Optional[bool] = None
    underline: Optional[bool] = None


@dataclass
class Frame:
    """Frame highlight border (Icon and ThemeLine only).

    Maps to ``<FrameStyle>`` in ANX XML.
    """
    color: Optional[Union[int, str, Color]] = None  # FrameStyle.Colour (default 16764057 = light yellow)
    margin: Optional[int] = None    # FrameStyle.Margin (default 2)
    visible: Optional[bool] = None  # FrameStyle.Visible (default False)


@dataclass
class Show:
    """Sub-item visibility flags shown in ANB's item panel.

    Maps to ``<SubItem Type="...">`` children inside ``<SubItemCollection>``.
    Each field defaults to ``None`` — the builder uses ANB's library defaults
    when unset (``label=True``, all others ``False``).
    """
    description: Optional[bool] = None  # SubItemDescription
    grades: Optional[bool] = None       # SubItemGrades
    label: Optional[bool] = None        # SubItemLabel
    date: Optional[bool] = None         # SubItemDateTime
    source_ref: Optional[bool] = None   # SubItemSourceReference
    source_type: Optional[bool] = None  # SubItemSourceType
    pin: Optional[bool] = None          # SubItemPin


# ── Settings groups ──────────────────────────────────────────────────────────

@dataclass
class ChartCfg:
    """Core <Chart> XML attributes."""
    bg_color: Optional[Union[int, str, Color]] = None  # BackColour
    bg_filled: Optional[bool] = None             # IsBackColourFilled
    label_merge_rule: Optional[str] = None       # LabelRule
    icon_quality: Optional[str] = None           # TypeIconDrawingMode
    rigorous: Optional[bool] = None              # Rigorous
    id_reference_linking: Optional[bool] = None  # IdReferenceLinking


@dataclass
class ViewCfg:
    """View / display toggles."""
    show_pages_boundaries: Optional[bool] = None  # ShowPages
    show_all: Optional[bool] = None               # ShowAllFlag
    hidden_items: Optional[str] = None            # HiddenItemsVisibility
    cover_sheet_on_open: Optional[bool] = None    # CoverSheetShowOnOpen
    time_bar: Optional[bool] = None               # TimeBarVisible


@dataclass
class GridCfg:
    """Grid settings."""
    width: Optional[float] = None     # GridWidthSize
    height: Optional[float] = None    # GridHeightSize
    snap: Optional[bool] = None       # SnapToGrid
    visible: Optional[bool] = None    # GridVisibleOnAllViews


@dataclass
class WiringCfg:
    """Theme/event wiring rendering."""
    distance_far: Optional[float] = None          # WiringDistanceFar
    distance_near: Optional[float] = None         # WiringDistanceNear
    height: Optional[float] = None                # WiringHeight
    spacing: Optional[float] = None               # WiringSpacing
    use_height_for_theme_icon: Optional[bool] = None  # UseWiringHeightForThemeIcon


@dataclass
class LinksCfg:
    """ANB chart-level link defaults."""
    spacing: Optional[float] = None                          # DefaultLinkSpacing
    use_default_spacing_when_dragging: Optional[bool] = None # UseDefaultLinkSpacingWhenDragging
    blank_labels: Optional[bool] = None                      # BlankLinkLabels
    sum_numeric_labels: Optional[bool] = None                # LabelSumNumericLinks


@dataclass
class TimeCfg:
    """Time / timezone defaults."""
    default_date: Optional[str] = None         # DefaultDate
    default_datetime: Optional[str] = None     # DefaultDateTimeForNewChart
    tick_rate: Optional[float] = None          # DefaultTickRate
    local_tz: Optional[bool] = None            # UseLocalTimeZone
    hide_matching_tz_format: Optional[bool] = None  # HideMatchingTimeZoneFormat


@dataclass
class SummaryCfg:
    """Document metadata (Summary fields + Origin fields folded in)."""
    title: Optional[str] = None       # SummaryFieldTitle
    subject: Optional[str] = None     # SummaryFieldSubject
    author: Optional[str] = None      # SummaryFieldAuthor
    keywords: Optional[str] = None    # SummaryFieldKeywords
    category: Optional[str] = None    # SummaryFieldCategory
    comments: Optional[str] = None    # SummaryFieldComments
    template: Optional[str] = None    # SummaryFieldTemplate
    created: Optional[str] = None     # CreatedDate
    revision: Optional[int] = None    # RevisionNumber
    edit_time: Optional[int] = None   # EditTime
    last_print: Optional[str] = None  # LastPrintDate
    last_save: Optional[str] = None   # LastSaveDate
    custom_properties: List[CustomProperty] = field(default_factory=list)


@dataclass
class LegendCfg:
    """Legend appearance and position."""
    show: Optional[bool] = None      # LegendShown
    x: Optional[int] = None          # X
    y: Optional[int] = None          # Y
    arrange: Optional[str] = None    # Arrange (LegendArrangementWide/Tall/Square)
    valign: Optional[str] = None     # VerticalAlignment
    halign: Optional[str] = None     # HorizontalAlignment
    font: Font = field(default_factory=Font)


@dataclass
class GeoMapCfg:
    """Geographic positioning config — maps entity attribute values to lat/lon
    coordinates for canvas positioning and/or ANB mapping attribute injection.

    ``mode`` controls what gets set:
    - ``'position'``: sets x,y canvas coordinates only
    - ``'latlon'``: injects Latitude/Longitude attributes with semantic types only
    - ``'both'``: sets x,y AND injects lat/lon attributes
    """
    attribute_name: Optional[str] = None     # Entity attribute to match against
    mode: Optional[str] = None               # 'position', 'latlon', 'both' (default 'both')
    width: Optional[int] = None              # Canvas projection area width (default 3000)
    height: Optional[int] = None             # Canvas projection area height (default 2000)
    spread_radius: Optional[int] = None      # Same-key entity circle spread (default 0)
    data: Optional[Dict[str, List[float]]] = None       # Inline key -> [lat, lon]
    data_file: Optional[str] = None          # External file path for data
    accent_insensitive: Optional[bool] = None  # Fold diacritics during matching (default True)


@dataclass
class ExtraCfg:
    """ANXWritter-only knobs (not written to ANX XML)."""
    entity_auto_color: Optional[bool] = None       # Distribute HSV hues
    link_match_entity_color: Optional[bool] = None # Set link line to to_id entity color
    arrange: Optional[str] = None                  # Auto-layout: 'radial' (default) / 'circle' / 'grid' / 'random' / 'fr' / 'forceatlas2' / 'tree'
    layout_scale: Optional[float] = None           # Uniform spread multiplier across all arrange modes (default 1.0)
    link_arc_offset: Optional[int] = None          # Parallel-link arc offset
    geo_map: Optional[GeoMapCfg] = None            # Geographic positioning


# Forward references resolved after all classes defined — see bottom of Settings class
_SETTINGS_GROUPS: Dict[str, type] = {}


@dataclass
class Settings:
    """Top-level chart settings — groups all configuration in one place.

    Use ``Settings.from_dict(d)`` to convert a nested dict (e.g. parsed from
    YAML/JSON config files) into a Settings instance.
    """
    chart: ChartCfg = field(default_factory=ChartCfg)
    font: Font = field(default_factory=Font)
    view: ViewCfg = field(default_factory=ViewCfg)
    grid: GridCfg = field(default_factory=GridCfg)
    wiring: WiringCfg = field(default_factory=WiringCfg)
    links_cfg: LinksCfg = field(default_factory=LinksCfg)
    time: TimeCfg = field(default_factory=TimeCfg)
    summary: SummaryCfg = field(default_factory=SummaryCfg)
    legend_cfg: LegendCfg = field(default_factory=LegendCfg)
    extra_cfg: ExtraCfg = field(default_factory=ExtraCfg)

    @classmethod
    def from_dict(cls, d: Optional[dict]) -> "Settings":
        """Convert a nested dict into a ``Settings`` instance.

        Unknown top-level keys raise ``TypeError``. Unknown nested keys also
        raise ``TypeError`` via the dataclass constructor — no silent drops.
        Nested dataclass fields (e.g. legend_cfg.font) are handled automatically.
        """
        s = cls()
        if not d:
            return s

        for key, raw in d.items():
            if raw is None:
                continue

            if key not in _SETTINGS_GROUPS:
                raise TypeError(
                    f"Unknown settings group {key!r}. "
                    f"Valid groups: {', '.join(sorted(_SETTINGS_GROUPS.keys()))}."
                )

            group_cls = _SETTINGS_GROUPS[key]
            if isinstance(raw, group_cls):
                # Already the right dataclass type — use directly
                setattr(s, key, raw)
            elif isinstance(raw, dict):
                # Use _build_group for automatic nested dataclass handling
                setattr(s, key, _build_group(group_cls, raw))
            else:
                raise TypeError(
                    f"settings[{key!r}] must be a dict or {group_cls.__name__}, "
                    f"got {type(raw).__name__}"
                )

        return s

    def merge_from_dict(self, d: Optional[dict]) -> None:
        """Update this Settings instance in place from a nested dict.

        Only fields explicitly present in ``d`` with non-None values are
        overwritten — None and missing fields keep their current value.
        Used by ``apply_config`` for layered configs.
        Nested dataclass fields (e.g. legend_cfg.font) are handled automatically.
        """
        if not d:
            return

        for key, raw in d.items():
            if raw is None:
                continue

            if key not in _SETTINGS_GROUPS:
                raise TypeError(
                    f"Unknown settings group {key!r}. "
                    f"Valid groups: {', '.join(sorted(_SETTINGS_GROUPS.keys()))}."
                )

            if not isinstance(raw, dict):
                raise TypeError(f"settings[{key!r}] must be a dict, got {type(raw).__name__}")

            # Use _merge_group for automatic nested dataclass handling
            target = getattr(self, key)
            _merge_group(target, raw)


# Populate _SETTINGS_GROUPS now that all classes are defined
_SETTINGS_GROUPS.update({
    'chart':      ChartCfg,
    'font':       Font,
    'view':       ViewCfg,
    'grid':       GridCfg,
    'wiring':     WiringCfg,
    'links_cfg':  LinksCfg,
    'time':       TimeCfg,
    'summary':    SummaryCfg,
    'legend_cfg': LegendCfg,
    'extra_cfg':  ExtraCfg,
})


@dataclass
class TimeZone:
    """ANB timezone with id (1-122) and display name.

    ``id`` is ANB's internal UniqueID integer (1-122, NOT the Windows registry Index).
    ``name`` is a cosmetic display string - ANB resolves timezone from ``id`` alone.

    Key values: 1=UTC, 32=GMT, 55=Argentina(UTC-3), 65=Japan(UTC+9),
    27=EST(UTC-5), 17=CET(UTC+1), 37=IST(UTC+5:30), 21=China(UTC+8).
    Full mapping in ``anxwritter/timezones.json``.
    """
    id: int
    name: str


@dataclass
class CustomProperty:
    """Chart-level custom property (name/value pair).

    Appears in the chart's Summary > Description > Custom tab.
    Always stored as Type="String" in the ANX XML.
    """
    name: str
    value: str


@dataclass
class Card:
    """Evidence card attached to an entity or link.

    ``entity_id`` and ``link_id`` are internal routing fields used at build time
    to attach a loose Card to the correct entity or link. They are NOT written to XML.
    """

    summary: Optional[str] = None
    date: Optional[str] = None              # 'yyyy-MM-dd'
    time: Optional[str] = None              # 'HH:mm:ss'
    description: Optional[str] = None
    source_ref: Optional[str] = None
    source_type: Optional[str] = None
    grade_one: Optional[Union[int, str]] = None  # 0-based index OR grade name string (resolved at build time)
    grade_two: Optional[Union[int, str]] = None
    grade_three: Optional[Union[int, str]] = None
    datetime_description: Optional[str] = None  # Free-text date/time description (e.g. 'About 3pm')
    timezone: Optional[TimeZone] = None     # ANB timezone (id + name)
    entity_id: Optional[str] = None         # INTERNAL ONLY — routes card to entity at build time. NOT written to XML.
    link_id: Optional[str] = None           # INTERNAL ONLY — routes card to link by Link.link_id at build time. NOT written to XML.


@dataclass
class AttributeClass:
    """Chart-level configuration for a named attribute type."""

    name: str = ''
    type: Optional[AttributeType] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    decimal_places: Optional[int] = None
    show_value: Optional[bool] = None
    show_date: Optional[bool] = None
    show_time: Optional[bool] = None
    show_seconds: Optional[bool] = None
    show_if_set: Optional[bool] = None
    show_class_name: Optional[bool] = None
    show_symbol: Optional[bool] = None
    visible: Optional[bool] = None
    is_user: Optional[bool] = None
    user_can_add: Optional[bool] = None
    user_can_remove: Optional[bool] = None
    icon_file: Optional[str] = None
    semantic_type: Optional[str] = None   # SemanticTypeGuid — NCName from i2 Semantic Type Library
    merge_behaviour: Optional[MergeBehaviour] = None
    paste_behaviour: Optional[MergeBehaviour] = None
    font: Font = field(default_factory=Font)


@dataclass
class Link:
    """A link between two entities."""

    from_id: str = ''
    to_id: str = ''
    type: Optional[str] = None
    arrow: Optional[str] = None             # 'ArrowOnHead', 'ArrowOnTail', 'ArrowOnBoth'
    label: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    description: Optional[str] = None
    strength: Optional[str] = None
    line_color: Optional[Union[int, str, Color]] = None
    line_width: Optional[int] = None
    offset: Optional[int] = None
    ordered: Optional[bool] = None
    grade_one: Optional[Union[int, str]] = None  # 0-based index OR grade name string (resolved at build time)
    grade_two: Optional[Union[int, str]] = None
    grade_three: Optional[Union[int, str]] = None
    attributes: dict = field(default_factory=dict)
    cards: List[Card] = field(default_factory=list)
    label_font: Font = field(default_factory=Font)
    timezone: Optional[TimeZone] = None     # ANB timezone (id + name)
    source_ref: Optional[str] = None
    source_type: Optional[str] = None
    show: Show = field(default_factory=Show)
    background: Optional[bool] = None
    datetime_description: Optional[str] = None  # Free-text date/time description shown on ChartItem
    show_datetime_description: Optional[bool] = None
    datetime_format: Optional[str] = None     # Name of a DateTimeFormat or inline format string
    sub_text_width: Optional[float] = None
    use_sub_text_width: Optional[bool] = None
    multiplicity: Optional[Union[str, Multiplicity]] = None        # 'MultiplicityMultiple', 'MultiplicitySingle', 'MultiplicityDirected' — use Multiplicity enum
    fan_out: Optional[int] = None            # arc spread for parallel links (integer, world coords)
    theme_wiring: Optional[Union[str, ThemeWiring]] = None       # 'KeepsAtEventHeight', 'ReturnsToThemeHeight', etc. — use ThemeWiring enum
    link_id: Optional[str] = None           # INTERNAL ONLY — used to target loose Card attachment. NOT written to XML.
    semantic_type: Optional[str] = None     # Per-instance SemanticTypeGuid override on <Link> element. Overrides LinkType-level semantic type.


@dataclass
class Strength:
    """Named strength entry defining a line dash/dot style."""

    name: str = ''
    dot_style: DotStyle = DotStyle.SOLID


@dataclass
class GradeCollection:
    """Wrapper for a grade collection (grades_one/two/three).

    ``default`` is the grade name assigned to items that don't set an explicit
    grade index.  When ``None`` and ``items`` is non-empty, a ``'-'`` sentinel
    is appended automatically at build time.  ``default`` must reference a name
    in ``items`` — validation rejects unknown names.
    """

    default: Optional[str] = None
    items: List[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __bool__(self) -> bool:
        return bool(self.items) or self.default is not None

    def __eq__(self, other) -> bool:
        if isinstance(other, GradeCollection):
            return self.default == other.default and self.items == other.items
        return NotImplemented


@dataclass
class StrengthCollection:
    """Wrapper for the chart strength list.

    ``default`` is the strength name used as fallback for items that don't set
    an explicit strength.  When ``None`` and custom strengths are defined, a
    ``'-'`` sentinel replaces the built-in ``'Default'`` fallback.
    """

    default: Optional[str] = None
    items: List[Strength] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)


@dataclass
class EntityType:
    """Pre-defined entity type with explicit icon, color, and representation.

    Only ``name`` is required. All other fields are optional — when omitted,
    the corresponding XML attribute is not emitted and i2 uses its own defaults.

    ``color`` maps to the ``Colour`` attribute on ``<EntityType>`` which i2 uses
    as the **line color** for the type.

    ``shade_color`` maps to ``IconShadingColour`` on ``<EntityType>`` — the icon
    tint color applied by default to entities of this type. An explicit
    ``IconShadingColour`` set on ``<IconStyle>`` (per-entity) always wins over the
    type-level value.
    """

    name: str = ''
    icon_file: Optional[str] = None
    color: Optional[Union[int, str, Color]] = None        # Colour (line color) — COLORREF int, named color, or '#RRGGBB'
    shade_color: Optional[Union[int, str, Color]] = None   # IconShadingColour — COLORREF int, named color, or '#RRGGBB'
    representation: Optional[Union[str, Representation]] = None             # 'Icon', 'Box', 'Circle', 'ThemeLine', 'EventFrame', 'TextBlock', 'Label'
    semantic_type: Optional[str] = None              # SemanticTypeGuid — NCName from i2 Semantic Type Library


@dataclass
class LinkType:
    """Pre-defined link type with explicit color."""

    name: str = ''
    color: Optional[Union[int, str, Color]] = None   # COLORREF int, named color, or '#RRGGBB'
    semantic_type: Optional[str] = None         # SemanticTypeGuid — NCName from i2 Semantic Type Library


@dataclass
class PaletteAttributeEntry:
    """An attribute class entry in a palette with an optional pre-filled value.

    When ``value`` is ``None``, the entry represents the attribute class itself
    (no default value). When set, the entry appears in ANB's palette with a
    pre-filled value the user can drag onto chart items.
    """

    name: str = ''                          # AttributeClass name
    value: Optional[str] = None             # Pre-filled value (None = class only)


@dataclass
class Palette:
    """A named palette containing entity types, link types, and attribute entries.

    Palettes populate ANB's "Insert from Palette" UI panel. Each palette can
    contain a selection of entity types, link types, attribute class definitions,
    and attribute entries with pre-filled values.
    """

    name: str = 'Standard'
    locked: bool = False
    entity_types: List[str] = field(default_factory=list)
    link_types: List[str] = field(default_factory=list)
    attribute_classes: List[str] = field(default_factory=list)
    attribute_entries: List[PaletteAttributeEntry] = field(default_factory=list)


@dataclass
class LegendItem:
    """One row in the chart legend."""

    name: str = ''
    item_type: Optional[Union[str, LegendItemType]] = 'Font'  # 'Font','Text','Icon','Attribute','Line','Link','TimeZone','IconFrame' (legacy Title Case) or LegendItemType enum / lowercase
    color: Optional[Union[int, str, Color]] = None
    line_width: Optional[int] = None
    dash_style: Optional[str] = None
    arrows: Optional[str] = None
    image_name: Optional[str] = None
    shade_color: Optional[Union[int, str, Color]] = None
    font: Font = field(default_factory=Font)


@dataclass
class DateTimeFormat:
    """Named date/time display format for the chart-level DateTimeFormatCollection."""

    name: str = ''
    format: str = ''


@dataclass
class SemanticEntity:
    """Custom entity semantic type (``lcx:Type`` under the Entity root).

    Used to define custom entries in the ``lcx:LibraryCatalogue`` for entity types.
    The ``kind_of`` field references the parent type name (must exist in the standard
    catalogue loaded from a reference .ant/.anx, or in another SemanticEntity).
    """

    name: str = ''                                   # TypeName (required)
    kind_of: str = ''                                # Parent entity type name (required)
    guid: Optional[str] = None                       # Override GUID (auto-generated if None)
    abstract: bool = False
    synonyms: Optional[List[str]] = None             # → Documentation > lcx:Synonym
    description: Optional[str] = None                # → Documentation > Description


@dataclass
class SemanticLink:
    """Custom link semantic type (``lcx:Type`` under the Link root).

    Same structure as SemanticEntity but for the Link hierarchy.
    """

    name: str = ''
    kind_of: str = ''                                # Parent link type name
    guid: Optional[str] = None
    abstract: bool = False
    synonyms: Optional[List[str]] = None
    description: Optional[str] = None


@dataclass
class SemanticProperty:
    """Custom property semantic type (``lcx:Property``).

    Property semantic types have four abstract roots: Abstract Text, Abstract Number,
    Abstract Date & Time, Abstract Flag. ``base_property`` must reference an existing
    property name from the standard catalogue or another SemanticProperty.
    """

    name: str = ''                                   # PropertyName (required)
    base_property: str = ''                          # Parent property name (required)
    guid: Optional[str] = None                       # Override GUID (auto-generated if None)
    abstract: bool = False
    synonyms: Optional[List[str]] = None
    description: Optional[str] = None
