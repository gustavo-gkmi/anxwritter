"""
Typed dataclasses for all eight i2 ANB entity representation types.

These classes form the public entity API for the redesigned anxwritter package.
``_BaseEntity`` is an internal base and is not exported publicly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional, Union

if TYPE_CHECKING:
    from .models import Card

from .enums import Color
from .models import Font, Frame, Show, TimeZone


@dataclass
class _BaseEntity:
    """Internal base class shared by all entity representation types.

    Not part of the public API — subclass one of the concrete types instead.
    """

    id: str = ""
    """Unique entity identity (maps to ``Entity.Identity`` in ANX XML)."""

    type: str = ""
    """Entity type name, e.g. ``'Person'`` or ``'Vehicle'``."""

    label: Optional[str] = None
    """Display label shown beneath the icon. Defaults to ``id`` in the XML builder."""

    date: Optional[str] = None
    """Date string in ``yyyy-MM-dd`` format."""

    time: Optional[str] = None
    """Time string in ``HH:mm:ss`` format."""

    description: Optional[str] = None
    """Free-text entity description."""

    ordered: Optional[bool] = None
    """``Ordered`` on ``<ChartItem>`` — when ``True``, ANB uses **Controladores**
    mode (ordered with date & time). Requires ``date`` and ``time`` to be set."""

    strength: Optional[str] = None
    """Named strength for the entity border, e.g. ``'Default'`` or ``'Confirmed'``."""

    grade_one: Optional[Union[int, str]] = None
    """Source reliability grade. Accepts a 0-based index into ``chart.grades_one``
    or the grade name string (e.g. ``'Reliable'``) — the name is resolved to its
    index at validate/build time."""

    grade_two: Optional[Union[int, str]] = None
    """Information reliability grade. Accepts a 0-based index into
    ``chart.grades_two`` or the grade name string."""

    grade_three: Optional[Union[int, str]] = None
    """Third grading dimension. Accepts a 0-based index into ``chart.grades_three``
    or the grade name string."""

    x: Optional[int] = None
    """Manual canvas X position. When set, auto-layout is skipped for this entity."""

    y: Optional[int] = None
    """Manual canvas Y position. When set, auto-layout is skipped for this entity."""

    attributes: dict = field(default_factory=dict)
    """Attribute dict, e.g. ``{'phone': '555-0001', 'calls': 12}``.

    Type is inferred from the Python value:
    ``str`` → Text, ``int``/``float`` → Number, ``bool`` → Flag, ``datetime`` → DateTime.
    """

    cards: List["Card"] = field(default_factory=list)
    """Evidence cards attached to this entity."""

    label_font: Font = field(default_factory=Font)
    """Font styling for the entity's display label (color, bg_color, name, size,
    bold, italic, strikeout, underline). Uses the shared ``Font`` dataclass."""

    timezone: Optional[TimeZone] = None
    """TimeZone for the ChartItem — uses the ``TimeZone`` dataclass with ``id``
    (int, ANB UniqueID 1-122) and ``name`` (str, cosmetic display string).
    Example: ``TimeZone(id=1, name='UTC')``."""

    source_ref: Optional[str] = None
    """Source reference string."""

    source_type: Optional[str] = None
    """Source type label string (should match an entry in ``chart.source_types``)."""

    show: Show = field(default_factory=Show)
    """Sub-item visibility flags for ANB's item panel. Uses the shared ``Show`` dataclass.
    Each field defaults to ``None`` (ANB library default: ``label=True``, all others ``False``)."""

    background: Optional[bool] = None
    """``CIStyle.Background`` — makes the entity a non-selectable background image."""

    datetime_description: Optional[str] = None
    """Free-text description of the date/time (e.g. ``'About 3pm'``).
    Written as the ``DateTimeDescription`` attribute on ``<ChartItem>``.
    Use with ``show_datetime_description=True`` to display it instead of raw values."""

    show_datetime_description: Optional[bool] = None
    """``CIStyle.ShowDateTimeDescription`` — when ``True``, displays the formatted
    date/time description string instead of the raw date/time values."""

    datetime_format: Optional[str] = None
    """Name of a registered ``DateTimeFormat``, or an inline format string.
    When it matches a name in the chart's ``DateTimeFormatCollection``, the builder
    emits ``DateTimeFormatReference`` on ``<CIStyle>``. Otherwise emits an inline
    ``DateTimeFormat`` attribute."""

    sub_text_width: Optional[float] = None
    """``CIStyle.SubTextWidth`` — exact effect not fully confirmed."""

    use_sub_text_width: Optional[bool] = None
    """``CIStyle.UseSubTextWidth`` — exact effect not fully confirmed."""

    semantic_type: Optional[str] = None
    """Per-instance ``SemanticTypeGuid`` on ``<Entity>`` element. Overrides the
    type-level semantic type set on ``EntityType``. Resolved to a GUID at build
    time from the catalogue or custom semantic entity definitions."""


@dataclass
class Icon(_BaseEntity):
    """Icon entity — the most common representation; displays as an image with a label.

    The ``color`` field sets the icon shading color (``IconShadingColour`` in ANX XML).
    The ``icon`` field overrides the ANB icon key resolved from the entity type name.
    When set, the builder emits ``OverrideTypeIcon="true"`` and ``TypeIconName`` on
    ``<IconStyle>`` so the entity displays this icon instead of its type's default.
    """

    color: Optional[Union[int, str, Color]] = None
    """Icon shading color — color name from ``VALID_SHADING_COLORS``, ``#RRGGBB`` hex,
    or a COLORREF integer.

    Note: This is named ``color`` (not ``shade_color`` like ThemeLine/EventFrame)
    because Icon is the most common entity type and ``color`` is simpler for users.
    ThemeLine/EventFrame use ``shade_color`` to disambiguate from their other color
    fields (bg_color, line_color). All map to ``IconShadingColour`` in ANX XML."""

    icon: Optional[str] = None
    """ANB icon file key, e.g. ``'person'``. When set, overrides the type's default icon
    for this specific entity instance via ``OverrideTypeIcon``/``TypeIconName``."""

    frame: Frame = field(default_factory=Frame)
    """Frame highlight border. Uses the shared ``Frame`` dataclass (color, margin, visible)."""

    text_x: Optional[int] = None
    """Horizontal offset of the label text relative to the icon. Omitted from XML when ``None``."""

    text_y: Optional[int] = None
    """Vertical offset of the label text relative to the icon. Omitted from XML when ``None``."""

    enlargement: Optional[str] = None
    """Icon enlargement size — use ``Enlargement`` enum or raw string. Omitted from XML when ``None``."""



@dataclass
class Box(_BaseEntity):
    """Box entity — rectangular shape with an optional fill and border."""

    bg_color: Optional[Union[int, str, Color]] = None
    """Fill color — color name, ``#RRGGBB`` hex, or COLORREF integer. Default ``16777215`` (white)."""

    filled: Optional[bool] = None
    """Whether the shape is filled. Default ``False`` for Box."""

    line_color: Optional[Union[int, str, Color]] = None
    """Border/line color — color name, ``#RRGGBB`` hex, or COLORREF integer."""

    line_width: Optional[int] = None
    """Border line thickness in pixels. Default ``1``."""

    width: Optional[int] = None
    """Box width in canvas units (integer direct). Default ``100``."""

    height: Optional[int] = None
    """Box height in canvas units (integer direct). Default ``100``."""

    depth: Optional[int] = None
    """Optional 3-D depth for the box shape."""


@dataclass
class Circle(_BaseEntity):
    """Circle entity — elliptical shape."""

    bg_color: Optional[Union[int, str, Color]] = None
    """Fill color — color name, ``#RRGGBB`` hex, or COLORREF integer. Default ``16777215`` (white)."""

    filled: Optional[bool] = None
    """Whether the shape is filled. Default ``True``."""

    line_width: Optional[int] = None
    """Border line thickness in pixels. Default ``1``."""

    diameter: Optional[int] = None
    """Circle diameter in canvas units divided by 100 → decimal inches. Default ``138``."""

    autosize: Optional[bool] = None
    """Whether the circle auto-sizes to fit its label. Default ``False``."""


@dataclass
class ThemeLine(_BaseEntity):
    """ThemeLine entity — a horizontal band spanning the full chart width.

    Multiple ThemeLines without an explicit ``y`` position are auto-assigned
    Y offsets of 0, 30, 60, … in order of appearance.
    """

    shade_color: Optional[Union[int, str, Color]] = None
    """Icon shading color — color name, ``#RRGGBB`` hex, or COLORREF integer."""

    line_color: Optional[Union[int, str, Color]] = None
    """Line/border color — color name, ``#RRGGBB`` hex, or COLORREF integer."""

    line_width: Optional[int] = None
    """Line thickness in pixels. Default ``3``."""

    frame: Frame = field(default_factory=Frame)
    """Frame highlight border. Uses the shared ``Frame`` dataclass (color, margin, visible)."""

    enlargement: Optional[str] = None
    """Icon enlargement size — use ``Enlargement`` enum or raw string. Omitted from XML when ``None``."""

    icon: Optional[str] = None
    """ANB icon file key, e.g. ``'person'``. When set, overrides the type's default icon
    for this specific ThemeLine via ``OverrideTypeIcon``/``TypeIconName``."""


@dataclass
class EventFrame(_BaseEntity):
    """EventFrame entity — a time-bounded region on the timeline."""

    shade_color: Optional[Union[int, str, Color]] = None
    """Icon shading color — color name, ``#RRGGBB`` hex, or COLORREF integer."""

    bg_color: Optional[Union[int, str, Color]] = None
    """Fill color — color name, ``#RRGGBB`` hex, or COLORREF integer. Default ``16777215`` (white)."""

    filled: Optional[bool] = None
    """Whether the shape is filled. Default ``True``."""

    line_color: Optional[Union[int, str, Color]] = None
    """Border/line color — color name, ``#RRGGBB`` hex, or COLORREF integer."""

    line_width: Optional[int] = None
    """Line thickness in pixels. Default ``1``."""

    enlargement: Optional[str] = None
    """Icon enlargement size — use ``Enlargement`` enum or raw string. Omitted from XML when ``None``."""

    icon: Optional[str] = None
    """ANB icon file key, e.g. ``'person'``. When set, overrides the type's default icon
    for this specific EventFrame via ``OverrideTypeIcon``/``TypeIconName``."""


@dataclass
class TextBlock(_BaseEntity):
    """TextBlock entity — a free-standing text box on the canvas."""

    bg_color: Optional[Union[int, str, Color]] = None
    """Fill color — color name, ``#RRGGBB`` hex, or COLORREF integer. Default ``16777215`` (white)."""

    filled: Optional[bool] = None
    """Whether the text box is filled. Default ``True``."""

    line_color: Optional[Union[int, str, Color]] = None
    """Border/line color — color name, ``#RRGGBB`` hex, or COLORREF integer."""

    line_width: Optional[int] = None
    """Border line thickness in pixels. Default ``1``."""

    alignment: Optional[str] = None
    """Text alignment: ``'TextAlignCentre'``, ``'TextAlignLeft'``, or ``'TextAlignRight'``.
    Default ``'TextAlignCentre'``."""

    width: Optional[int] = None
    """Width in canvas units (divided by 100 → inches). Default ``138``."""

    height: Optional[int] = None
    """Height in canvas units (divided by 100 → inches). Default ``79``."""


@dataclass
class Label(_BaseEntity):
    """Label entity — a transparent text overlay using TextBlock XML elements.

    The border and fill are set to the chart background color with ``Filled="false"``
    to approximate i2's native Label appearance.
    """

    bg_color: Optional[Union[int, str, Color]] = None
    """Fill color — color name, ``#RRGGBB`` hex, or COLORREF integer (rendered transparent by the builder)."""

    filled: Optional[bool] = None
    """Whether the shape is filled. Default ``True``."""

    line_color: Optional[Union[int, str, Color]] = None
    """Border/line color — color name, ``#RRGGBB`` hex, or COLORREF integer."""

    line_width: Optional[int] = None
    """Border line thickness in pixels. Default ``1``."""

    alignment: Optional[str] = None
    """Text alignment: ``'TextAlignCentre'``, ``'TextAlignLeft'``, or ``'TextAlignRight'``.
    Default ``'TextAlignCentre'``."""

    width: Optional[int] = None
    """Width in canvas units (divided by 100 → inches). Default ``100``."""

    height: Optional[int] = None
    """Height in canvas units (divided by 100 → inches). Default ``39``."""
