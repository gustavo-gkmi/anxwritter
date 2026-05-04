"""
Intermediate resolved dataclasses for the compute-then-emit architecture.

These hold final string/int values ready for XML emission — no Optional
ambiguity, no enums to resolve, no color names to parse. Entity/link
objects are resolved into these before any transforms (auto-color, layout,
etc.) are applied, then emitted to XML in a single linear pass.

Internal only — not part of the public API.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, Union


class ResolvedAttr(NamedTuple):
    """A resolved attribute ready for XML emission.

    - ``class_name``: The attribute class name (e.g. 'Phone')
    - ``ac_ref_id``: The AttributeClass ID reference for XML
    - ``value_str``: The serialized value string
    """
    class_name: str
    ac_ref_id: str
    value_str: str


@dataclass
class ResolvedCard:
    """Fully resolved evidence card — ready for XML emission.

    Date/time parsed via ``_format_datetime`` (same multi-format parser used
    for entities and links).  Grade indices, source fields, and timezone
    fields are copied as-is but available for future validation/transforms.
    """
    summary: Optional[str] = None
    date_set: bool = False
    time_set: bool = False
    datetime_str: Optional[str] = None          # ISO datetime or None
    datetime_description: Optional[str] = None
    source_ref: Optional[str] = None
    source_type: Optional[str] = None
    description: Optional[str] = None           # Card body text (XML 'Text' attr)
    grade_one: Optional[int] = None
    grade_two: Optional[int] = None
    grade_three: Optional[int] = None
    timezone_id: Optional[int] = None           # ANB UniqueID 1-122
    timezone_name: Optional[str] = None


@dataclass
class ResolvedChartItem:
    """Shared fields for both entity and link ChartItems."""
    ci_id: str = ''
    label: str = ''
    description: str = ''                       # '' if unset
    date_set: bool = False
    time_set: bool = False
    datetime_str: Optional[str] = None          # ISO datetime or None
    datetime_description: str = ''              # '' if unset
    ordered: bool = False
    source_ref: str = ''
    source_type: str = ''
    grade_one: Optional[int] = None
    grade_two: Optional[int] = None
    grade_three: Optional[int] = None
    attributes: List[ResolvedAttr] = field(default_factory=list)
    cards: List[ResolvedCard] = field(default_factory=list)
    # CIStyle fields (all Optional — None = omit from XML)
    background: Optional[bool] = None
    show_datetime_description: Optional[bool] = None
    sub_text_width: Optional[float] = None
    use_sub_text_width: Optional[bool] = None
    datetime_format: Optional[str] = None
    # Font overrides (all Optional — None = omit; colors are resolved COLORREF ints)
    label_color: Optional[int] = None
    label_bg_color: Optional[int] = None
    label_face: Optional[str] = None
    label_size: Optional[int] = None
    label_bold: Optional[bool] = None
    label_italic: Optional[bool] = None
    label_strikeout: Optional[bool] = None
    label_underline: Optional[bool] = None
    # SubItem visibility (all Optional — None = use ANB default)
    show_description: Optional[bool] = None
    show_grades: Optional[bool] = None
    show_label: Optional[bool] = None
    show_date: Optional[bool] = None
    show_source_ref: Optional[bool] = None
    show_source_type: Optional[bool] = None
    show_pin: Optional[bool] = None
    # Timezone (passthrough — same format as entity.timezone)
    timezone: Any = None
    # Strength name (passed to visual representation style)
    strength: str = 'Default'


@dataclass
class ResolvedEntity(ResolvedChartItem):
    """Fully resolved entity — all colors as COLORREF ints, icon names
    translated, datetime parsed, cards resolved."""
    entity_int_id: int = 0
    identity: str = ''
    entity_type: str = ''
    representation: str = ''                    # 'Icon', 'Box', etc.
    # All representation-specific style fields.  Keys vary by type:
    #   shade_color (int), type_icon_name (str), bg_color (int),
    #   filled (bool), line_color (int), line_width (int),
    #   width (int), height (int), depth (int), diameter (float),
    #   autosize (bool), alignment (str),
    #   frame_color (int), frame_margin (float), frame_visible (bool),
    #   enlargement (str), text_x (float), text_y (float)
    representation_style: Dict[str, Any] = field(default_factory=dict)
    semantic_guid: Optional[str] = None
    x: int = 0                                  # layout-resolved position
    y: int = 0


@dataclass
class ResolvedLink(ResolvedChartItem):
    """Fully resolved link — arrow enum resolved, line color as COLORREF int,
    connection style deduped, cards resolved."""
    from_int_id: int = 0
    to_int_id: int = 0
    from_ci_id: str = ''
    to_ci_id: str = ''
    link_type: str = ''
    arrow: str = 'ArrowNone'                    # full ANB name
    line_width: int = 1
    line_color: int = 0                         # resolved COLORREF int
    strength: str = 'Default'
    offset: int = 0
    conn_id: Optional[str] = None
    semantic_guid: Optional[str] = None
