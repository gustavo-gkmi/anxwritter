"""
anxwritter — Convert typed Python objects to i2 Analyst's Notebook Exchange (.anx) files.

Quick start
-----------
::

    from anxwritter import ANXChart

    chart = ANXChart()

    chart.add_icon(id='Alice', type='Person', color='Blue',
                   attributes={'phone': '555-0001'})
    chart.add_icon(id='Bob', type='Person')

    chart.add_link(from_id='Alice', to_id='Bob', type='Call',
                   arrow='->', date='2024-01-15',
                   attributes={'duration': 120})

    chart.to_anx('output/my_chart')   # writes output/my_chart.anx
"""

from importlib.metadata import version, metadata, PackageNotFoundError

from loguru import logger

from .chart import ANXChart
from .errors import ANXValidationError, ErrorType
from .colors import NAMED_COLORS, color_to_colorref, rgb_to_colorref
from .enums import VALID_SHADING_COLORS, MergeBehaviour, DotStyle, Enlargement, AttributeType, Multiplicity, ThemeWiring, ArrowStyle, Representation, LegendItemType, Color
from .entities import Icon, Box, Circle, ThemeLine, EventFrame, TextBlock, Label
from .models import (
    Card, Link, AttributeClass, Strength, LegendItem, EntityType, LinkType,
    Palette, PaletteAttributeEntry, DateTimeFormat,
    SemanticEntity, SemanticLink, SemanticProperty,
    Font, Frame, Show, TimeZone, CustomProperty,
    GradeCollection, StrengthCollection,
    Settings, ChartCfg, ViewCfg, GridCfg, WiringCfg, LinksCfg, TimeCfg,
    SummaryCfg, LegendCfg, ExtraCfg, GeoMapCfg,
)

try:
    __version__ = version("anxwritter")
    _meta = metadata("anxwritter")
    __repo_url__ = ""
    for val in _meta.get_all("Project-URL") or []:
        label, url = val.split(", ", 1)
        if label == "Repository":
            __repo_url__ = url
            break
except PackageNotFoundError:
    __version__ = "0.0.0"
    __repo_url__ = ""

logger.disable("anxwritter")

__all__ = [
    # Version
    '__version__',
    # Main class
    'ANXChart',
    'ANXValidationError',
    'ErrorType',
    # Entity classes
    'Icon', 'Box', 'Circle', 'ThemeLine', 'EventFrame', 'TextBlock', 'Label',
    # Chart item classes
    'Card', 'Link', 'AttributeClass', 'Strength', 'LegendItem',
    'GradeCollection', 'StrengthCollection',
    'EntityType', 'LinkType',
    'Palette', 'PaletteAttributeEntry',
    'DateTimeFormat',
    'SemanticEntity', 'SemanticLink', 'SemanticProperty',
    # Settings dataclasses
    'Font', 'Frame', 'Show', 'TimeZone', 'CustomProperty', 'Settings',
    'ChartCfg', 'ViewCfg', 'GridCfg', 'WiringCfg', 'LinksCfg', 'TimeCfg',
    'SummaryCfg', 'LegendCfg', 'ExtraCfg', 'GeoMapCfg',
    # Enums
    'MergeBehaviour',
    'DotStyle',
    'Enlargement',
    'AttributeType',
    'Multiplicity',
    'ThemeWiring',
    'ArrowStyle',
    'Representation',
    'LegendItemType',
    'Color',
    # Color helpers
    'VALID_SHADING_COLORS',
    'NAMED_COLORS',
    'color_to_colorref',
    'rgb_to_colorref',
]
