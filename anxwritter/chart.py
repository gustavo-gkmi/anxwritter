"""
ANXChart — converts typed entity/link objects to i2 Analyst's Notebook Exchange (.anx) files.

The produced .anx file can be opened directly in i2 ANB 9+ via File > Open.
All chart data is embedded in the .anx file — no separate CSV is needed.

Quick start
-----------
::

    from anxwritter import ANXChart
    from anxwritter.entities import Icon
    from anxwritter.models import Link

    chart = ANXChart()

    chart.add_icon(id='Alice', type='Person', color='Blue',
                   attributes={'phone': '555-0001', 'age': 39})
    chart.add_icon(id='Bob', type='Person')

    chart.add_link(from_id='Alice', to_id='Bob',
                   type='Call', arrow='ArrowOnHead', date='2024-01-15',
                   attributes={'duration': 120})

    chart.to_anx('output/my_chart')
"""
from __future__ import annotations

import dataclasses
import json
import math
import yaml
import os
import time
from datetime import datetime as _datetime, date as _date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger

from .builder import ANXBuilder
from .colors import color_to_colorref
from .entities import _BaseEntity, Icon, Box, Circle, ThemeLine, EventFrame, TextBlock, Label
from .enums import DotStyle, Representation
from .errors import ANXValidationError
from ._i2_interop import LATITUDE_GUID, LONGITUDE_GUID, GRID_REFERENCE_GUID
from .models import (
    Card, Link, AttributeClass, Strength, LegendItem, EntityType, LinkType,
    Palette, PaletteAttributeEntry, DateTimeFormat,
    SemanticEntity, SemanticLink, SemanticProperty,
    GradeCollection, StrengthCollection,
    Settings, Font, Frame, Show, TimeZone, CustomProperty,
)
from .timing import PhaseTimer
from .utils import _enum_val
from .transforms import (
    compute_auto_colors,
    apply_auto_colors,
    build_entity_color_map,
    compute_link_offsets,
    compute_theme_line_y_offsets,
    apply_grade_defaults,
    resolve_grade_names,
    resolve_geo_data,
    match_geo_entities,
    compute_geo_positions,
    inject_geo_attributes,
)


# ── Helper functions ──────────────────────────────────────────────────────────

# Fallback datetime formats tried by ``_parse_attr_datetime`` when
# ``datetime.fromisoformat`` rejects the value (mostly relevant on Python
# 3.10, where fromisoformat only handles a strict subset).  Mirrors the
# date / time formats the rest of the library accepts so an attribute value
# is parseable in any form a ``date`` or ``time`` field already accepts.
_ATTR_DATETIME_FORMATS: Tuple[str, ...] = (
    '%Y-%m-%dT%H:%M:%S.%f',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%d %H:%M:%S.%f',
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d',
    '%d/%m/%Y',
    '%Y%m%d',
)


def _parse_attr_datetime(val: Any) -> Optional[_datetime]:
    """Parse *val* as a ``datetime`` using a permissive ISO 8601 chain.

    Returns the ``datetime`` instance on success.  Returns ``None`` if *val*
    is not a string we can parse — callers should leave the original value
    in place so downstream type-inference / validation can flag the mismatch
    with a meaningful error rather than silently swapping the type.

    Already-typed ``datetime`` inputs are passed through unchanged so this
    helper is safe to call on the Python API path too.
    """
    if isinstance(val, _datetime):
        return val
    if not isinstance(val, str):
        return None
    s = val.strip()
    if not s:
        return None
    # Strip a trailing 'Z' (UTC marker) since fromisoformat in Python 3.10
    # rejects it.  We don't preserve the offset here — attribute values are
    # serialized to the builder's UTC-naïve xsd:dateTime format anyway.
    candidate = s[:-1] if s.endswith('Z') else s
    try:
        return _datetime.fromisoformat(candidate)
    except (ValueError, AttributeError):
        pass
    for fmt in _ATTR_DATETIME_FORMATS:
        try:
            return _datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _str_or_none(val: Any) -> Optional[str]:
    """Return str(val) stripped, or None if val is empty/NaN."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    s = str(val).strip()
    return s if s else None


def _int_or_none(val: Any) -> Optional[int]:
    """Return int(val), or None if val is None/NaN."""
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _settings_to_clean_dict(settings: Settings) -> dict:
    """Convert a Settings dataclass to a nested dict with None values dropped.

    Empty groups (every field is None) are omitted entirely.
    Used for ``to_config_dict`` and conflict comparison.
    """
    out: Dict[str, Any] = {}
    for fld in dataclasses.fields(settings):
        group = getattr(settings, fld.name)
        if group is None:
            continue
        if dataclasses.is_dataclass(group):
            inner: Dict[str, Any] = {}
            for sub in dataclasses.fields(group):
                val = getattr(group, sub.name)
                if val is None:
                    continue
                if dataclasses.is_dataclass(val):
                    nested = {k: v for k, v in dataclasses.asdict(val).items() if v is not None}
                    if nested:
                        inner[sub.name] = nested
                elif isinstance(val, list) and not val:
                    continue
                else:
                    inner[sub.name] = val
            if inner:
                out[fld.name] = inner
    return out


def _infer_attr_type(value: Any) -> str:
    """Infer i2 attribute type string from a Python value."""
    if isinstance(value, bool):
        return 'Flag'
    if isinstance(value, (int, float)):
        return 'Number'
    # date catches both datetime.datetime and datetime.date.
    if isinstance(value, _date):
        return 'DateTime'
    return 'Text'


# ── Main class ────────────────────────────────────────────────────────────────

class ANXChart:
    """Converts typed entity/link objects to an i2 Analyst's Notebook ANX file.

    Usage
    -----
    1. Instantiate: ``chart = ANXChart()``
    2. Add entities: ``chart.add_icon(id='A', type='Person')``
    3. Add links: ``chart.add_link(from_id='A', to_id='B', type='Call')``
    4. Export: ``chart.to_anx('output/my_chart')``
    """

    def __init__(
        self,
        settings: Optional[Union[Settings, Dict[str, Any]]] = None,
        *,
        config: Optional[Dict[str, Any]] = None,
        config_file: Optional[Union[str, Path]] = None,
    ) -> None:
        self._entities: List[_BaseEntity] = []
        self._links: List[Link] = []
        self._loose_cards: List[Card] = []
        self._attribute_classes: List[AttributeClass] = []
        self.strengths: StrengthCollection = StrengthCollection(
            items=[Strength(name='Default', dot_style=DotStyle.SOLID)]
        )
        self._legend_items: List[LegendItem] = []
        self._entity_types: List[EntityType] = []
        self._link_types: List[LinkType] = []
        self._palettes: List[Palette] = []
        self._datetime_formats: List[DateTimeFormat] = []
        self._semantic_entities: List['SemanticEntity'] = []
        self._semantic_links: List['SemanticLink'] = []
        self._semantic_properties: List['SemanticProperty'] = []
        self.grades_one: GradeCollection = GradeCollection()
        self.grades_two: GradeCollection = GradeCollection()
        self.grades_three: GradeCollection = GradeCollection()
        self.source_types: List[str] = []

        # Settings: accept Settings instance, dict (converted via from_dict), or None.
        if settings is None:
            self.settings: Settings = Settings()
        elif isinstance(settings, Settings):
            self.settings = settings
        elif isinstance(settings, dict):
            self.settings = Settings.from_dict(settings)
        else:
            raise TypeError(
                f"settings must be a Settings instance, a dict, or None — "
                f"got {type(settings).__name__}"
            )

        # Config tracking — conflict detection between config and data
        self._config_locked: Dict[str, Dict[str, dict]] = {}  # section -> {name: asdict}
        self._config_locked_grades: Dict[str, GradeCollection] = {}  # grade key -> locked GradeCollection
        self._config_locked_source_types: Optional[List[str]] = None  # locked source_types list
        self._config_conflicts: List[Dict[str, Any]] = []
        self._has_config: bool = False

        if config_file:
            self.apply_config_file(config_file)
        elif config:
            self.apply_config(config)

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    @staticmethod
    def _dc_to_clean_dict(obj) -> dict:
        """Convert a dataclass to a dict with None values removed."""
        return {k: v for k, v in dataclasses.asdict(obj).items() if v is not None}

    def _apply_config(
        self,
        data: dict,
        *,
        is_config: bool = True,
        replace: bool = False,
    ) -> None:
        """Apply config sections from a dict to this chart.

        When *is_config* is True, names are registered into ``_config_locked``
        so that subsequent data-file loading can detect conflicts.
        When *is_config* is False and ``_has_config`` is True, incoming names
        are checked against the locked set — identical entries are silently
        skipped, differing entries are recorded as conflicts. *replace* is
        ignored in data mode.

        When *replace* is True and *is_config* is True, every section the
        layer mentions is replaced wholesale instead of merged. Sections the
        layer does not mention survive untouched. This is the per-section
        opt-in for the rare "narrow the list" case.

        ``entities`` and ``links`` keys are silently ignored.
        """
        # ── settings: deep merge into Settings dataclass ──
        incoming_settings = data.get('settings')
        if incoming_settings is not None:
            if isinstance(incoming_settings, Settings):
                if is_config and replace:
                    # Replace mode: discard existing settings, keep only what
                    # this layer specifies.
                    self.settings = incoming_settings
                else:
                    # Merge so we don't replace nested defaults wholesale.
                    self.settings.merge_from_dict(dataclasses.asdict(incoming_settings))
            elif isinstance(incoming_settings, dict):
                if is_config and replace:
                    self.settings = Settings.from_dict(incoming_settings)
                else:
                    self.settings.merge_from_dict(incoming_settings)
            else:
                raise TypeError(
                    f"config['settings'] must be a Settings instance or dict, "
                    f"got {type(incoming_settings).__name__}"
                )

        # ── Strengths (handles new dict format with default/items) ──
        raw_strengths = data.get('strengths')
        if raw_strengths is not None:
            strength_items: list = []
            if is_config and replace:
                # Wipe pre-populated 'Default' + any earlier-layer strengths
                # so this layer fully replaces the section.
                self.strengths = StrengthCollection()
                self._config_locked.pop('strengths', None)
            if isinstance(raw_strengths, StrengthCollection):
                # Default: later wins if non-None, else keep earlier's.
                if raw_strengths.default is not None:
                    self.strengths.default = raw_strengths.default
                strength_items = raw_strengths.items
            elif isinstance(raw_strengths, dict):
                if raw_strengths.get('default') is not None:
                    self.strengths.default = raw_strengths['default']
                strength_items = raw_strengths.get('items', [])
            # Parse and add each strength item
            locked = self._config_locked.get('strengths', {})
            for raw in strength_items:
                if isinstance(raw, dict):
                    obj = Strength(**{k: v for k, v in raw.items() if v is not None})
                elif isinstance(raw, Strength):
                    obj = raw
                else:
                    continue
                name = obj.name
                clean = self._dc_to_clean_dict(obj)
                if is_config:
                    self.add_strength(obj)
                    if name:
                        locked[name] = clean
                else:
                    if self._has_config and name and name in locked:
                        if clean != locked[name]:
                            self._config_conflicts.append({
                                'type': 'config_conflict',
                                'section': 'strengths',
                                'name': name,
                                'message': (
                                    f"Data redefines '{name}' in strengths with different "
                                    f"specs than config. Remove from data file or match config."
                                ),
                                'config_value': locked[name],
                                'data_value': clean,
                            })
                    else:
                        self.add_strength(obj)
            if is_config and locked:
                self._config_locked['strengths'] = locked

        # ── Helper for named-object sections ──
        # Every adder performs upsert-by-name (later wins), so layered
        # configs cleanly override earlier definitions of the same entity
        # type / link type / attribute class / etc.
        _NAMED_SECTIONS = {
            'entity_types': (EntityType, self.add_entity_type, '_entity_types'),
            'link_types': (LinkType, self.add_link_type, '_link_types'),
            'attribute_classes': (AttributeClass, self.add_attribute_class, '_attribute_classes'),
            'datetime_formats': (DateTimeFormat, self.add_datetime_format, '_datetime_formats'),
            'semantic_entities': (SemanticEntity, self.add_semantic_entity, '_semantic_entities'),
            'semantic_links': (SemanticLink, self.add_semantic_link, '_semantic_links'),
            'semantic_properties': (SemanticProperty, self.add_semantic_property, '_semantic_properties'),
        }

        # Sections whose dataclasses contain a `font: Font` field — when the
        # source is a raw dict (YAML/JSON), convert the nested dict to a
        # Font instance before constructing the parent dataclass.
        _SECTIONS_WITH_FONT = {'attribute_classes'}

        for section, (cls, adder, attr_name) in _NAMED_SECTIONS.items():
            if section not in data:
                continue
            items = data.get(section, [])
            if is_config and replace:
                # Wipe the section before processing this layer's entries.
                getattr(self, attr_name).clear()
                self._config_locked.pop(section, None)
            locked = self._config_locked.get(section, {})

            for raw in items:
                if isinstance(raw, dict):
                    cleaned = {k: v for k, v in raw.items() if v is not None}
                    if section in _SECTIONS_WITH_FONT and 'font' in cleaned:
                        if isinstance(cleaned['font'], dict):
                            cleaned['font'] = Font(**{
                                k: v for k, v in cleaned['font'].items() if v is not None
                            })
                    obj = cls(**cleaned)
                elif isinstance(raw, cls):
                    obj = raw
                else:
                    continue

                name = obj.name
                if not name:
                    # Will be caught by validate() later
                    adder(obj)
                    continue

                clean = self._dc_to_clean_dict(obj)

                if is_config:
                    # Config mode: upsert (later wins per name) and lock
                    adder(obj)
                    locked[name] = clean
                else:
                    # Data mode: check against locked names
                    if self._has_config and name in locked:
                        if clean != locked[name]:
                            self._config_conflicts.append({
                                'type': 'config_conflict',
                                'section': section,
                                'name': name,
                                'message': (
                                    f"Data redefines '{name}' in {section} with different "
                                    f"specs than config. Remove from data file or match config."
                                ),
                                'config_value': locked[name],
                                'data_value': clean,
                            })
                        # else: identical → silent skip
                    else:
                        adder(obj)

            if is_config and locked:
                self._config_locked[section] = locked

        # ── palettes: always append (no natural key) ──
        if 'palettes' in data:
            if is_config and replace:
                self._palettes.clear()
            for raw in data.get('palettes', []):
                if isinstance(raw, dict):
                    d = {k: v for k, v in raw.items() if v is not None}
                    ae = d.get('attribute_entries')
                    if ae and isinstance(ae, list):
                        d['attribute_entries'] = [
                            PaletteAttributeEntry(**e) if isinstance(e, dict) else e
                            for e in ae
                        ]
                    self._palettes.append(Palette(**d))
                elif isinstance(raw, Palette):
                    self._palettes.append(raw)

        # ── legend_items: always append (no natural key) ──
        if 'legend_items' in data and is_config and replace:
            self._legend_items.clear()
        for raw in data.get('legend_items', []):
            if isinstance(raw, dict):
                # Map 'label' to 'name' for backward compat with YAML configs
                li_dict = {k: v for k, v in raw.items() if v is not None}
                if 'label' in li_dict and 'name' not in li_dict:
                    li_dict['name'] = li_dict.pop('label')
                # Convert font dict (YAML/JSON path) to Font instance
                if 'font' in li_dict and isinstance(li_dict['font'], dict):
                    li_dict['font'] = Font(**{
                        k: v for k, v in li_dict['font'].items() if v is not None
                    })
                self._legend_items.append(LegendItem(**li_dict))
            elif isinstance(raw, LegendItem):
                self._legend_items.append(raw)

        # ── grades ──
        # Default behavior: append items with case-sensitive exact-text dedup;
        # `default` field follows "later wins if non-None, else keep earlier's".
        # replace=True replaces the whole GradeCollection wholesale.
        for key in ('grades_one', 'grades_two', 'grades_three'):
            if key not in data:
                continue
            val = data.get(key)
            if val is None:
                continue

            if isinstance(val, GradeCollection):
                incoming_default = val.default
                incoming_items = list(val.items)
            elif isinstance(val, dict):
                incoming_default = val.get('default')
                incoming_items = list(val.get('items', []))
            else:
                continue

            if is_config and replace:
                # Replace mode: the layer's GradeCollection becomes the
                # whole section. Wipe existing items + locked entry first.
                gc = GradeCollection(default=incoming_default, items=incoming_items)
                setattr(self, key, gc)
                self._config_locked_grades[key] = gc
                continue

            if is_config:
                # Append + dedup mode: extend existing items, preserve order,
                # skip exact-text matches already present.
                current: GradeCollection = getattr(self, key)
                existing = set(current.items)
                for item in incoming_items:
                    if item not in existing:
                        current.items.append(item)
                        existing.add(item)
                if incoming_default is not None:
                    current.default = incoming_default
                # Re-lock with the merged state so conflict detection sees
                # what the data file will be compared against.
                self._config_locked_grades[key] = GradeCollection(
                    default=current.default, items=list(current.items),
                )
            else:
                # Data mode: keep existing config-vs-data conflict semantics.
                gc = GradeCollection(default=incoming_default, items=incoming_items)
                if self._has_config and key in self._config_locked_grades:
                    locked = self._config_locked_grades[key]
                    if gc.items != locked.items or gc.default != locked.default:
                        self._config_conflicts.append({
                            'type': 'config_conflict',
                            'section': key,
                            'name': key,
                            'message': (
                                f"Data redefines '{key}' with different values than config. "
                                f"Remove from data file or match config."
                            ),
                            'config_value': {'default': locked.default, 'items': locked.items},
                            'data_value': {'default': gc.default, 'items': gc.items},
                        })
                    # else: identical → silent skip
                else:
                    setattr(self, key, gc)

        # ── source_types ──
        # Default behavior: append with case-sensitive exact-text dedup.
        # replace=True replaces the list wholesale.
        if 'source_types' in data:
            val = data.get('source_types')
            if val is not None:
                val = list(val)

                if is_config and replace:
                    self.source_types = val
                    self._config_locked_source_types = list(val)
                elif is_config:
                    existing = set(self.source_types)
                    for item in val:
                        if item not in existing:
                            self.source_types.append(item)
                            existing.add(item)
                    self._config_locked_source_types = list(self.source_types)
                else:
                    if self._has_config and self._config_locked_source_types is not None:
                        if val != self._config_locked_source_types:
                            self._config_conflicts.append({
                                'type': 'config_conflict',
                                'section': 'source_types',
                                'name': 'source_types',
                                'message': (
                                    "Data redefines 'source_types' with different values than config. "
                                    "Remove from data file or match config."
                                ),
                                'config_value': self._config_locked_source_types,
                                'data_value': val,
                            })
                        # else: identical → silent skip
                    else:
                        self.source_types = val

        if is_config:
            self._has_config = True

    def _apply_data(self, data: dict) -> None:
        """Apply a full data dict (config sections + entities + links).

        Config sections are processed via ``_apply_config(is_config=False)``
        (conflict detection active when a config was previously applied).
        Entities and links are parsed and added to the chart.
        """
        # Apply config sections from the data dict
        self._apply_config(data, is_config=False)

        # ── Pre-compute the set of attribute names declared as `type: datetime`
        # in the registered AttributeClass collection.  Used by `_coerce_attrs`
        # below to convert ISO 8601 strings to ``datetime`` instances on the
        # JSON path (JSON has no native datetime literal).  The lookup runs
        # AFTER `_apply_config` so it sees both config-locked declarations and
        # any `attribute_classes` entries the data file itself contributes.
        _declared_dt_attrs: set = {
            ac.name for ac in self._attribute_classes
            if ac.name and ac.type is not None
            and _enum_val(ac.type).lower() == 'datetime'
        }

        def _coerce_attrs(attrs: Any) -> Any:
            """Coerce string values to ``datetime`` for attributes declared as
            ``type: datetime``.  Pass-through for everything else."""
            if not _declared_dt_attrs or not isinstance(attrs, dict):
                return attrs
            out = dict(attrs)
            for name in _declared_dt_attrs:
                if name in out:
                    parsed = _parse_attr_datetime(out[name])
                    if parsed is not None:
                        out[name] = parsed
                    # else: leave the original value — `check_attr_types`
                    # (validation.py) will surface the mismatch as a
                    # `type_conflict` error rather than silently muting it.
            return out

        # ── Parse entities ──
        def _norm_dc(dc_cls: type, val: Any) -> Any:
            """Convert a dict to *dc_cls* by passing its keys as kwargs.

            Pass-through if *val* is None or already an instance of *dc_cls*.
            None-valued keys in the dict are stripped so the dataclass picks
            up its own defaults instead of being assigned ``None`` explicitly
            (the constructors are written for that pattern).
            """
            if val is None or isinstance(val, dc_cls):
                return val
            if isinstance(val, dict):
                return dc_cls(**{k: v for k, v in val.items() if v is not None})
            return val

        def _norm_timezone(tz: Any) -> Optional[TimeZone]:
            """Convert timezone dict to TimeZone dataclass."""
            if tz is None or isinstance(tz, TimeZone):
                return tz
            if isinstance(tz, dict):
                return TimeZone(id=tz['id'], name=tz['name'])
            return tz

        def _norm_cards(raw: list) -> list:
            # Card.coerce_list handles dict→Card conversion (Card.__post_init__
            # normalizes nested timezone dicts), and rejects non-Card/non-dict
            # items with a clear TypeError. Same coercion runs from the Python
            # API path via _BaseEntity/Link __post_init__, so YAML and direct
            # construction stay in lockstep.
            return Card.coerce_list(raw)

        # Fields shared by entities and links that the YAML/JSON path needs to
        # convert from raw dicts back into typed dataclasses.  Keep this in sync
        # with the corresponding fields on _BaseEntity / Link.
        _NESTED_DC_FIELDS = (
            ('label_font', Font),
            ('show',       Show),
            ('frame',      Frame),  # Icon / ThemeLine only — silently skipped on others
        )

        def _norm_chart_item_dict(d: dict) -> dict:
            """Normalize a raw entity- or link-shaped dict.

            Converts ``cards``, ``timezone``, ``label_font``, ``show``, and
            ``frame`` into their typed counterparts.  Coerces string-valued
            attributes whose names are declared ``type: datetime`` into Python
            ``datetime`` instances so JSON-sourced data behaves the same as
            YAML's native datetime literals.  Used for both entity rows (under
            ``entities.<rep_key>``) and link rows (under ``links``).
            """
            out = {k: v for k, v in d.items() if v is not None}
            if 'cards' in out and isinstance(out['cards'], list):
                out['cards'] = _norm_cards(out['cards'])
            if 'timezone' in out:
                out['timezone'] = _norm_timezone(out['timezone'])
            if 'attributes' in out:
                out['attributes'] = _coerce_attrs(out['attributes'])
            for fname, dc_cls in _NESTED_DC_FIELDS:
                if fname in out:
                    out[fname] = _norm_dc(dc_cls, out[fname])
            return out

        entities_data = data.get('entities', {})
        if isinstance(entities_data, dict):
            _ENTITY_MAP = {
                'icons': Icon,
                'boxes': Box,
                'circles': Circle,
                'theme_lines': ThemeLine,
                'event_frames': EventFrame,
                'text_blocks': TextBlock,
                'labels': Label,
            }
            for key, cls in _ENTITY_MAP.items():
                for d in entities_data.get(key, []):
                    norm = _norm_chart_item_dict(d)
                    # Frame is only valid on Icon/ThemeLine — drop it elsewhere
                    # to avoid TypeError from the dataclass constructor.
                    if 'frame' in norm and cls not in (Icon, ThemeLine):
                        norm.pop('frame')
                    self.add(cls(**norm))

        # ── Parse links ──
        for d in data.get('links', []):
            norm = _norm_chart_item_dict(d)
            # Link has no `frame` field — drop it if present.
            norm.pop('frame', None)
            self.add(Link(**norm))

        # ── Parse loose cards (top-level `loose_cards` key) ──
        # Mirrors `chart.add_card(entity_id=..., link_id=..., **fields)`.
        # Useful when cards come from a different data source than entities
        # (e.g. a separate CSV or DB query in an ETL pipeline).  The
        # loader normalises `timezone`, coerces datetime attribute values
        # via the same path as inline cards, and routes by entity_id /
        # link_id at build time (validated by `validate_loose_cards`).
        for raw in data.get('loose_cards', []):
            if isinstance(raw, Card):
                self._loose_cards.append(raw)
                continue
            if not isinstance(raw, dict):
                continue
            cd = {k: v for k, v in raw.items() if v is not None}
            if 'timezone' in cd:
                cd['timezone'] = _norm_timezone(cd['timezone'])
            self._loose_cards.append(Card(**cd))

    # ------------------------------------------------------------------
    # Config public API
    # ------------------------------------------------------------------

    def apply_config(self, data: dict, *, replace: bool = False) -> None:
        """Apply a config dict to this chart. Locks names for conflict detection.

        Only config sections are applied (settings, entity_types, link_types,
        attribute_classes, strengths, legend_items, grades, source_types).
        ``entities`` and ``links`` keys are silently ignored.

        Layering rules (when this is the second-or-later config layer):

        - ``settings``: deep merge — only fields the layer sets overwrite.
        - ``entity_types``, ``link_types``, ``attribute_classes``,
          ``datetime_formats``, ``semantic_*``, ``strengths.items``:
          upsert by ``name`` — same name in a later layer replaces the entry,
          new names are appended.
        - ``strengths.default``, ``grades_*.default``: later wins if non-None,
          otherwise the earlier layer's default is kept.
        - ``source_types``, ``grades_one/two/three.items``: append with
          case-sensitive exact-text dedup. ``'Witness'`` and ``'witness'``
          both end up in the merged list — normalize strings if you layer
          across teams.
        - ``legend_items``, ``palettes``: append (no natural key, multiple
          rows with the same name are valid).

        When *replace* is True, every section the layer mentions is replaced
        wholesale instead of merged. Sections the layer does not mention
        survive untouched. Use this for the rare "narrow the list" case.

        No validation runs at load time. Call :meth:`validate` to lint the
        config (bad colors, duplicate names, malformed timezones, palette
        references to unknown attribute classes, etc.) without building XML —
        ``validate()`` walks every declared entity type, link type, attribute
        class, etc. regardless of whether any entity or link uses them.
        """
        self._apply_config(data, is_config=True, replace=replace)

    def apply_config_file(
        self,
        path: Union[str, Path],
        *,
        replace: bool = False,
    ) -> None:
        """Load a config file (JSON or YAML) and apply it to this chart.

        See :meth:`apply_config` for the full layering rules and the
        meaning of *replace*. Call :meth:`validate` after loading to
        catch schema errors before feeding the chart any data.
        """
        data = self._load_file(path)
        self.apply_config(data, replace=replace)

    @classmethod
    def from_config(cls, source: str) -> "ANXChart":
        """Create an ANXChart pre-loaded with config from a JSON or YAML string.

        Tries JSON first; falls back to YAML if JSON parsing fails.

        See :meth:`apply_config` for a note on validation.
        """
        try:
            data = json.loads(source)
        except (json.JSONDecodeError, ValueError):
            data = yaml.safe_load(source)
        chart = cls()
        chart.apply_config(data)
        return chart

    @classmethod
    def from_config_file(cls, path: Union[str, Path]) -> "ANXChart":
        """Create an ANXChart pre-loaded with config from a JSON or YAML file.

        Format detected by extension (.yaml/.yml -> YAML, else JSON).

        See :meth:`apply_config` for a note on validation.
        """
        chart = cls()
        chart.apply_config_file(path)
        return chart

    @staticmethod
    def _load_file(path: Union[str, Path]) -> dict:
        """Load a JSON or YAML file, auto-detecting format by extension.

        Rewrites relative paths in the loaded dict (currently only
        ``settings.extra_cfg.geo_map.data_file``) to be absolute, anchored
        at the loaded file's directory — matches the convention used by
        Compose, Cargo, GitLab CI, etc.
        """
        p = Path(path)
        text = p.read_text(encoding='utf-8')
        if p.suffix.lower() in ('.yaml', '.yml'):
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
        ANXChart._resolve_relative_paths(data, p.parent)
        return data

    @staticmethod
    def _resolve_relative_paths(data: Any, base_dir: Path) -> None:
        """Rewrite filesystem paths in a loaded data dict to be absolute.

        Anchors relative paths against ``base_dir`` (typically the directory
        of the file ``data`` was loaded from). Currently covers
        ``settings.extra_cfg.geo_map.data_file`` — the only path-valued
        field in the schema. Inline-Python construction of ``GeoMapCfg``
        keeps CWD-relative semantics (matches ``open()``); only file-loaded
        configs get this rewrite.

        Mutates ``data`` in place. Safe to call on any dict shape — non-dict
        intermediates and absolute paths are left alone.
        """
        if not isinstance(data, dict):
            return
        settings = data.get('settings')
        if not isinstance(settings, dict):
            return
        extra = settings.get('extra_cfg')
        if not isinstance(extra, dict):
            return
        geo_map = extra.get('geo_map')
        if not isinstance(geo_map, dict):
            return
        data_file = geo_map.get('data_file')
        if not isinstance(data_file, str) or not data_file:
            return
        p = Path(data_file)
        if p.is_absolute():
            return
        geo_map['data_file'] = str((base_dir / p).resolve())

    def to_config_dict(self) -> dict:
        """Export the current non-data configuration as a plain dict.

        Returns a dict containing only config sections (settings, entity_types,
        link_types, attribute_classes, strengths, legend_items, grades,
        source_types). Entities and links are not included.

        The ``settings`` block is exported with all None values stripped so the
        output dict only contains keys the user actually set.
        """
        result: Dict[str, Any] = {}

        settings_dict = _settings_to_clean_dict(self.settings)
        if settings_dict:
            result['settings'] = settings_dict

        _DEFAULT_STRENGTH = {'name': 'Default', 'dot_style': DotStyle.SOLID}

        for section, items in (
            ('entity_types', self._entity_types),
            ('link_types', self._link_types),
            ('attribute_classes', self._attribute_classes),
            ('strengths', self.strengths.items),
            ('legend_items', self._legend_items),
            ('datetime_formats', self._datetime_formats),
            ('semantic_entities', self._semantic_entities),
            ('semantic_links', self._semantic_links),
            ('semantic_properties', self._semantic_properties),
        ):
            if not items:
                continue
            cleaned = []
            for obj in items:
                d = self._dc_to_clean_dict(obj)
                # Skip the default pre-populated strength
                if section == 'strengths' and d == _DEFAULT_STRENGTH:
                    continue
                # Only normalize enum values; leave plain strings/ints unchanged.
                for k, v in d.items():
                    if hasattr(v, 'value'):
                        d[k] = _enum_val(v)
                cleaned.append(d)
            if cleaned:
                if section == 'strengths':
                    # Always emit the documented {default?, items} shape so
                    # _apply_config can round-trip it. A plain list is silently
                    # ignored by the strengths branch in _apply_config.
                    out: Dict[str, Any] = {'items': cleaned}
                    if self.strengths.default is not None:
                        out['default'] = self.strengths.default
                    result[section] = out
                else:
                    result[section] = cleaned

        for key in ('grades_one', 'grades_two', 'grades_three'):
            gc = getattr(self, key)
            if gc.items or gc.default is not None:
                d: Dict[str, Any] = {}
                if gc.default is not None:
                    d['default'] = gc.default
                if gc.items:
                    d['items'] = list(gc.items)
                result[key] = d

        if self.source_types:
            result['source_types'] = list(self.source_types)

        if self._palettes:
            pal_list = []
            for pal in self._palettes:
                d: Dict[str, Any] = {'name': pal.name}
                if pal.locked:
                    d['locked'] = True
                if pal.entity_types:
                    d['entity_types'] = list(pal.entity_types)
                if pal.link_types:
                    d['link_types'] = list(pal.link_types)
                if pal.attribute_classes:
                    d['attribute_classes'] = list(pal.attribute_classes)
                if pal.attribute_entries:
                    d['attribute_entries'] = [
                        self._dc_to_clean_dict(ae) for ae in pal.attribute_entries
                    ]
                pal_list.append(d)
            result['palettes'] = pal_list

        return result

    def to_config(self, path: str) -> str:
        """Export config to a JSON or YAML file.

        Format is determined by file extension (.yaml/.yml -> YAML, else JSON).
        Returns the absolute path of the written file.
        """
        p = Path(path)
        data = self.to_config_dict()

        if p.suffix.lower() in ('.yaml', '.yml'):
            text = yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)
        else:
            text = json.dumps(data, indent=2, ensure_ascii=False)

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return str(p.resolve())

    # ------------------------------------------------------------------
    # Generic dispatch
    # ------------------------------------------------------------------

    def add(self, item) -> None:
        """Generic dispatch: add a typed entity, link, attribute class, strength, legend item, or loose card."""
        if isinstance(item, _BaseEntity):
            self._entities.append(item)
        elif isinstance(item, Link):
            self._links.append(item)
        elif isinstance(item, Card):
            self._loose_cards.append(item)
        elif isinstance(item, AttributeClass):
            self._attribute_classes.append(item)
        elif isinstance(item, Strength):
            self.add_strength(item)
        elif isinstance(item, LegendItem):
            self._legend_items.append(item)
        elif isinstance(item, EntityType):
            self._entity_types.append(item)
        elif isinstance(item, LinkType):
            self._link_types.append(item)
        elif isinstance(item, Palette):
            self._palettes.append(item)
        elif isinstance(item, DateTimeFormat):
            self.add_datetime_format(item)
        elif isinstance(item, SemanticEntity):
            self._semantic_entities.append(item)
        elif isinstance(item, SemanticLink):
            self._semantic_links.append(item)
        elif isinstance(item, SemanticProperty):
            self._semantic_properties.append(item)
        else:
            raise TypeError(f"Cannot add item of type {type(item).__name__}")

    def add_all(self, items) -> None:
        """Add all items from any iterable."""
        for item in items:
            self.add(item)

    # ------------------------------------------------------------------
    # Entity convenience methods
    # ------------------------------------------------------------------

    def add_icon(self, **kwargs) -> None:
        """Add an Icon entity."""
        self.add(Icon(**kwargs))

    def add_box(self, **kwargs) -> None:
        """Add a Box entity."""
        self.add(Box(**kwargs))

    def add_circle(self, **kwargs) -> None:
        """Add a Circle entity."""
        self.add(Circle(**kwargs))

    def add_theme_line(self, **kwargs) -> None:
        """Add a ThemeLine entity."""
        self.add(ThemeLine(**kwargs))

    def add_event_frame(self, **kwargs) -> None:
        """Add an EventFrame entity."""
        self.add(EventFrame(**kwargs))

    def add_text_block(self, **kwargs) -> None:
        """Add a TextBlock entity."""
        self.add(TextBlock(**kwargs))

    def add_label(self, **kwargs) -> None:
        """Add a Label entity."""
        self.add(Label(**kwargs))

    def add_link(self, **kwargs) -> None:
        """Add a Link."""
        self.add(Link(**kwargs))

    def add_card(self, *, entity_id=None, link_id=None, **kwargs) -> None:
        """Add a loose Card that attaches to an entity or link at build time."""
        self._loose_cards.append(Card(entity_id=entity_id, link_id=link_id, **kwargs))

    @staticmethod
    def _upsert_by_name(collection: list, obj) -> None:
        """Replace an entry in ``collection`` that has the same ``name`` as
        ``obj``, or append ``obj`` if no match exists. Matches the semantics
        of layered config files: later definitions replace earlier ones with
        the same natural key, rather than appending a duplicate."""
        name = getattr(obj, 'name', None)
        if name:
            for i, existing in enumerate(collection):
                if getattr(existing, 'name', None) == name:
                    collection[i] = obj
                    return
        collection.append(obj)

    def add_attribute_class(self, name_or_obj=None, **kwargs) -> None:
        """Add or update an AttributeClass. Later calls with the same
        ``name`` replace the earlier entry."""
        if isinstance(name_or_obj, AttributeClass):
            obj = name_or_obj
        else:
            if name_or_obj is not None:
                kwargs['name'] = name_or_obj
            obj = AttributeClass(**kwargs)
        self._upsert_by_name(self._attribute_classes, obj)

    def add_strength(self, name_or_obj=None, **kwargs) -> None:
        """Add or update a Strength. Pass a Strength object or keyword args.

        If a Strength with the same name already exists (e.g. the pre-populated
        ``'Default'``), it is replaced rather than duplicated.
        """
        if isinstance(name_or_obj, Strength):
            obj = name_or_obj
        else:
            if name_or_obj is not None:
                kwargs['name'] = name_or_obj
            obj = Strength(**kwargs)
        # Replace existing with same name, or append
        for i, existing in enumerate(self.strengths.items):
            if existing.name == obj.name:
                self.strengths.items[i] = obj
                return
        self.strengths.items.append(obj)

    def add_datetime_format(self, name_or_obj=None, **kwargs) -> None:
        """Add or update a DateTimeFormat. Pass a DateTimeFormat object or keyword args.

        If a DateTimeFormat with the same name already exists, it is replaced
        rather than duplicated.
        """
        if isinstance(name_or_obj, DateTimeFormat):
            obj = name_or_obj
        else:
            if name_or_obj is not None:
                kwargs['name'] = name_or_obj
            obj = DateTimeFormat(**kwargs)
        for i, existing in enumerate(self._datetime_formats):
            if existing.name == obj.name:
                self._datetime_formats[i] = obj
                return
        self._datetime_formats.append(obj)

    def add_custom_property(self, name: str, value: str) -> None:
        """Add a chart-level custom property (name/value pair).

        Custom properties appear in the chart's Summary > Description > Custom tab.
        Always stored as Type="String" in the ANX XML.
        """
        self.settings.summary.custom_properties.append(
            CustomProperty(name=str(name), value=str(value))
        )

    def add_legend_item(self, name_or_obj=None, **kwargs) -> None:
        """Add a LegendItem. Pass a LegendItem object or keyword args."""
        if isinstance(name_or_obj, LegendItem):
            self._legend_items.append(name_or_obj)
        else:
            if name_or_obj is not None:
                kwargs['name'] = name_or_obj
            self._legend_items.append(LegendItem(**kwargs))

    def add_entity_type(self, name_or_obj=None, **kwargs) -> None:
        """Add or update an EntityType. Later calls with the same ``name``
        replace the earlier entry."""
        if isinstance(name_or_obj, EntityType):
            obj = name_or_obj
        else:
            if name_or_obj is not None:
                kwargs['name'] = name_or_obj
            obj = EntityType(**kwargs)
        self._upsert_by_name(self._entity_types, obj)

    def add_link_type(self, name_or_obj=None, **kwargs) -> None:
        """Add or update a LinkType. Later calls with the same ``name``
        replace the earlier entry."""
        if isinstance(name_or_obj, LinkType):
            obj = name_or_obj
        else:
            if name_or_obj is not None:
                kwargs['name'] = name_or_obj
            obj = LinkType(**kwargs)
        self._upsert_by_name(self._link_types, obj)

    def add_semantic_entity(self, name_or_obj=None, **kwargs) -> None:
        """Add or update a custom entity semantic type. Later calls with the
        same ``name`` replace the earlier entry."""
        if isinstance(name_or_obj, SemanticEntity):
            obj = name_or_obj
        else:
            if name_or_obj is not None:
                kwargs['name'] = name_or_obj
            obj = SemanticEntity(**kwargs)
        self._upsert_by_name(self._semantic_entities, obj)

    def add_semantic_link(self, name_or_obj=None, **kwargs) -> None:
        """Add or update a custom link semantic type. Later calls with the
        same ``name`` replace the earlier entry."""
        if isinstance(name_or_obj, SemanticLink):
            obj = name_or_obj
        else:
            if name_or_obj is not None:
                kwargs['name'] = name_or_obj
            obj = SemanticLink(**kwargs)
        self._upsert_by_name(self._semantic_links, obj)

    def add_semantic_property(self, name_or_obj=None, **kwargs) -> None:
        """Add or update a custom property semantic type. Later calls with
        the same ``name`` replace the earlier entry."""
        if isinstance(name_or_obj, SemanticProperty):
            obj = name_or_obj
        else:
            if name_or_obj is not None:
                kwargs['name'] = name_or_obj
            obj = SemanticProperty(**kwargs)
        self._upsert_by_name(self._semantic_properties, obj)

    def add_palette(self, name_or_obj=None, **kwargs) -> None:
        """Add a Palette. Pass a Palette object or keyword args.

        When keyword args include ``attribute_entries`` as a list of dicts,
        each dict is converted to a ``PaletteAttributeEntry``.
        """
        if isinstance(name_or_obj, Palette):
            self._palettes.append(name_or_obj)
        else:
            if name_or_obj is not None:
                kwargs['name'] = name_or_obj
            # Normalise attribute_entries from dicts
            ae = kwargs.get('attribute_entries')
            if ae and isinstance(ae, list):
                kwargs['attribute_entries'] = [
                    PaletteAttributeEntry(**e) if isinstance(e, dict) else e
                    for e in ae
                ]
            self._palettes.append(Palette(**kwargs))

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict) -> "ANXChart":
        """Create an ANXChart from a plain dict.

        Expected shape::

            {
                "settings": {"layout": "grid"},
                "entities": {
                    "icons": [{"id": "Alice", "type": "Person", ...}],
                    "boxes": [...],
                },
                "links": [{"from_id": "Alice", "to_id": "Bob", ...}],
                "attribute_classes": [...],
                "strengths": [...],
                "grades_one": [...],
                "grades_two": [...],
                "grades_three": [...],
                "source_types": [...],
                "legend_items": [...],
            }

        All keys are optional.
        """
        chart = cls()
        chart._apply_data(data)
        return chart

    @classmethod
    def from_json(cls, source: str) -> "ANXChart":
        """Create an ANXChart from a raw JSON string."""
        data = json.loads(source)
        return cls.from_dict(data)

    @classmethod
    def from_json_file(cls, path: Union[str, Path]) -> "ANXChart":
        """Create an ANXChart from a JSON file path.

        Relative paths inside the JSON (e.g. ``geo_map.data_file``) are
        anchored at the JSON file's directory.
        """
        p = Path(path)
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        cls._resolve_relative_paths(data, p.parent)
        return cls.from_dict(data)

    @classmethod
    def from_yaml(cls, source: str) -> "ANXChart":
        """Create an ANXChart from a raw YAML string."""
        data = yaml.safe_load(source)
        return cls.from_dict(data)

    @classmethod
    def from_yaml_file(cls, path: Union[str, Path]) -> "ANXChart":
        """Create an ANXChart from a YAML file path.

        Relative paths inside the YAML (e.g. ``geo_map.data_file``) are
        anchored at the YAML file's directory.
        """
        p = Path(path)
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        cls._resolve_relative_paths(data, p.parent)
        return cls.from_dict(data)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> List[Dict[str, Any]]:
        """Validate chart data without building XML.

        Returns:
            List of error dicts. Empty list means data is valid.
            Each dict has keys: ``type``, ``message``, and optionally
            ``location`` (e.g. ``"entities[2] (Icon)"``).

        Error types:
            ``missing_required`` — a required field is missing (id, type, from_id, to_id,
            label on LegendItem, name on EntityType/LinkType/Strength/AttributeClass).
            ``duplicate_id`` — the same entity id appears more than once.
            ``duplicate_name`` — duplicate name in EntityType, LinkType, Strength, or
            AttributeClass definitions.
            ``missing_entity`` — a link references an entity id that does not exist.
            ``missing_target`` — a loose card references a non-existent entity_id or link_id.
            ``unknown_color`` — a color string is not a valid name, hex, or int.
            ``invalid_date`` — a date string does not match yyyy-MM-dd.
            ``invalid_time`` — a time string does not match HH:mm:ss.
            ``type_conflict`` — the same attribute name is used with different inferred types.
            ``invalid_strength`` — a strength name is not registered in chart.strengths.
            ``invalid_arrow`` — an arrow value is not a recognised ArrowStyle string.
            ``grade_out_of_range`` — a grade index is negative or exceeds the collection size.
            ``self_loop`` — a link's from_id and to_id are the same.
            ``invalid_ordered`` — ordered=True on a link whose ends are not both ThemeLines.
            ``invalid_legend_type`` — a LegendItem has an unrecognised item_type.
            ``invalid_timezone`` — a timezone dict is malformed (missing id/name, id out of range).
            ``timezone_without_datetime`` — timezone set but date or time is missing.
            ``invalid_multiplicity`` — multiplicity value not a valid enum string.
            ``invalid_theme_wiring`` — theme_wiring value not a valid enum string.
            ``connection_conflict`` — links between the same pair set conflicting connection style values.
            ``config_conflict`` — data file redefines a config-locked name with different specs.
            ``invalid_geo_map`` — geo_map configuration error (missing attribute_name, invalid mode,
            lat/lon out of range, no data).
        """
        from .validation import (
            validate_strength_collection,
            validate_grade_collections,
            validate_entities,
            validate_links,
            validate_connection_conflicts,
            validate_loose_cards,
            validate_legend_items,
            validate_entity_types,
            validate_link_types,
            validate_datetime_formats,
            validate_attribute_classes,
            validate_palettes,
            validate_semantic_types,
        )

        errors: List[Dict[str, Any]] = []

        # Prepend config conflict errors (collected during _apply_config)
        if self._config_conflicts:
            errors.extend(self._config_conflicts)

        # Validate strength collection (default + duplicates)
        errors.extend(validate_strength_collection(self.strengths))

        # Validate grade collections (defaults exist in items)
        errors.extend(validate_grade_collections(
            self.grades_one, self.grades_two, self.grades_three
        ))

        # Validate datetime formats (duplicates, length limits)
        dtf_errors, dtf_names = validate_datetime_formats(self._datetime_formats)
        errors.extend(dtf_errors)

        # Shared state for cross-validation
        strength_names = {st.name for st in self.strengths.items if st.name}
        gc1_items = list(self.grades_one.items)
        gc2_items = list(self.grades_two.items)
        gc3_items = list(self.grades_three.items)
        attr_types: Dict[str, str] = {}

        # Validate entities (returns entity_ids and entity_classes for cross-refs)
        entity_errors, all_entity_ids, entity_classes = validate_entities(
            self._entities, strength_names, dtf_names,
            gc1_items, gc2_items, gc3_items, attr_types
        )
        errors.extend(entity_errors)

        # Validate links
        errors.extend(validate_links(
            self._links, all_entity_ids, entity_classes, strength_names, dtf_names,
            gc1_items, gc2_items, gc3_items, attr_types
        ))

        # Validate connection style conflicts
        errors.extend(validate_connection_conflicts(self._links))

        # Validate loose cards
        link_ids = {link.link_id for link in self._links if link.link_id}
        errors.extend(validate_loose_cards(self._loose_cards, all_entity_ids, link_ids))

        # Validate legend items
        errors.extend(validate_legend_items(self._legend_items))

        # Validate entity types (returns name->location map for palette validation)
        et_errors, et_names = validate_entity_types(self._entity_types)
        errors.extend(et_errors)

        # Validate link types (returns name->location map for palette validation)
        lt_errors, lt_names = validate_link_types(self._link_types)
        errors.extend(lt_errors)

        # Validate attribute classes (returns name->location map for palette validation)
        ac_errors, ac_names = validate_attribute_classes(
            self._attribute_classes, attr_types
        )
        errors.extend(ac_errors)

        # Validate palettes
        errors.extend(validate_palettes(
            self._palettes, et_names, lt_names, ac_names,
            self._attribute_classes, self._entities, self._links
        ))

        # Validate semantic types
        errors.extend(validate_semantic_types(
            self._semantic_entities, self._semantic_links, self._semantic_properties,
            self._entity_types, self._link_types, self._attribute_classes,
            self._entities, self._links,
        ))

        # Validate geo_map configuration
        from .validation import validate_geo_map
        errors.extend(validate_geo_map(
            self.settings.extra_cfg.geo_map, self._entities
        ))

        return errors

    # ------------------------------------------------------------------

    def to_anx(self, path: Union[str, Path]) -> str:
        """Build and write the ANX file.

        Args:
            path: Destination path (``str`` or ``pathlib.Path``).
                  ``.anx`` extension added automatically.

        Returns:
            Absolute path of the written file.

        Raises:
            ANXValidationError: If any rows had validation errors.
        """
        validation_errors = self.validate()
        if validation_errors:
            raise ANXValidationError(validation_errors)
        xml_content, build_errors = self._build_xml()
        path = str(path)
        if not path.lower().endswith('.anx'):
            path = path + '.anx'
        os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
        _t0_write = time.perf_counter()
        # Remove first to avoid stale trailing bytes (some platforms don't
        # fully truncate UTF-16 files when the new content is shorter).
        if os.path.exists(path):
            os.remove(path)
        with open(path, 'w', encoding='utf-16') as fh:
            fh.write(xml_content)
        logger.debug("File write: {path} ({elapsed:.4f}s)",
                      path=os.path.abspath(path),
                      elapsed=time.perf_counter() - _t0_write)
        return os.path.abspath(path)

    def to_xml(self) -> str:
        """Return the ANX XML as a string without writing a file.

        Raises:
            ANXValidationError: If any rows had validation errors.
        """
        validation_errors = self.validate()
        if validation_errors:
            raise ANXValidationError(validation_errors)
        xml_content, _build_errors = self._build_xml()
        return xml_content

    def _resolve_semantic_types(self, builder: 'ANXBuilder',
                               att_class_config: Dict[str, Dict[str, Any]],
                               ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Optional[str]], Dict[int, Optional[str]]]:
        """Resolve semantic type names to GUIDs and build the semantic_config dict.

        Delegates lookup state to ``SemanticResolver``; this method only owns
        mutation of ``builder._etype_meta``/``builder._ltype_meta``/``att_class_config``
        and the per-instance side-tables.

        Returns ``(semantic_config, entity_semantic_guids, link_semantic_guids)``.
        ``semantic_config`` is ``None`` when no semantic types are used.
        """
        from .semantic import SemanticResolver

        resolver = SemanticResolver(
            self._semantic_entities,
            self._semantic_links,
            self._semantic_properties,
        )

        # Resolve on EntityType defs — mutate the builder's stored metadata
        for et in self._entity_types:
            if et.semantic_type:
                resolved = resolver.resolve_type_name(et.semantic_type)
                meta = builder._etype_meta.get(et.name)
                if meta and resolved:
                    meta['semantic_type'] = resolved

        # Resolve on LinkType defs
        for lt in self._link_types:
            if lt.semantic_type:
                resolved = resolver.resolve_type_name(lt.semantic_type)
                lt_meta = builder._ltype_meta.get(lt.name)
                if lt_meta and resolved:
                    lt_meta['semantic_type'] = resolved

        # Resolve on AttributeClass defs
        for ac in self._attribute_classes:
            if ac.semantic_type:
                resolved = resolver.resolve_property_name(ac.semantic_type)
                if resolved:
                    cfg = att_class_config.get(ac.name)
                    if cfg:
                        cfg['semantic_type'] = resolved

        # Resolve per-instance semantic types (side-tables — no user-object mutation)
        entity_semantic_guids: Dict[str, Optional[str]] = {}
        for entity in self._entities:
            if entity.semantic_type and entity.id:
                entity_semantic_guids[entity.id] = resolver.resolve_type_name(entity.semantic_type)

        link_semantic_guids: Dict[int, Optional[str]] = {}
        for i, link in enumerate(self._links):
            if link.semantic_type:
                link_semantic_guids[i] = resolver.resolve_type_name(link.semantic_type)

        return resolver.build_config(), entity_semantic_guids, link_semantic_guids

    def _build_xml(self) -> Tuple[str, List[str]]:
        """Build the ANX XML, collecting validation errors without raising.

        Returns:
            (xml_string, errors) — errors is empty when all data is valid.
        """
        errors: List[str] = []
        timer = PhaseTimer("ANXChart._build_xml")
        s = self.settings

        with timer.phase("Initialize builder"):
            builder = ANXBuilder()
            entity_registry: Dict[str, Tuple[str, int]] = {}

        # ── chart.attribute_classes icon_file — register explicit icons ──
        with timer.phase("Register AC icons"):
            for ac in self._attribute_classes:
                if ac.name and ac.icon_file:
                    builder.set_att_class_icon(ac.name, ac.icon_file)

        # ── Pre-register DateTimeFormat definitions on builder ─────────────
        with timer.phase("Register datetime formats"):
            for dtf in self._datetime_formats:
                if dtf.name:
                    builder.register_datetime_format(dtf.name, dtf.format or '')

        # ── Pre-register EntityType / LinkType definitions ────────────────
        with timer.phase("Pre-register type defs"):
            _REP_MAP = {
                'Icon': Representation.ICON, 'Box': Representation.BOX,
                'Circle': Representation.CIRCLE, 'ThemeLine': Representation.THEME_LINE,
                'EventFrame': Representation.EVENT_FRAME, 'TextBlock': Representation.TEXT_BLOCK,
                'Label': Representation.LABEL,
            }
            for et in self._entity_types:
                if not et.name:
                    continue
                color_int = None
                if et.color is not None:
                    c = et.color
                    # color_to_colorref unwraps Color enums; isinstance int passthrough
                    color_int = c if isinstance(c, int) else color_to_colorref(c)
                shade_int = None
                if et.shade_color is not None:
                    sc = et.shade_color
                    shade_int = sc if isinstance(sc, int) else color_to_colorref(sc)
                rep = _REP_MAP.get(et.representation, Representation.ICON) if et.representation else None
                builder._entity_type_id(et.name, rep, et.icon_file, color_int, shade_int, et.semantic_type)

            for lt in self._link_types:
                if not lt.name:
                    continue
                color_int = None
                if lt.color is not None:
                    c = lt.color
                    color_int = c if isinstance(c, int) else color_to_colorref(c)
                builder._link_type_id(lt.name, color_int, lt.semantic_type)

        # ── Build att_class_config (needed by semantic resolution) ─────────
        with timer.phase("Build att_class_config"):
            att_class_config: Dict[str, Dict[str, Any]] = {}
            for ac in self._attribute_classes:
                if not ac.name:
                    continue
                d: Dict[str, Any] = {}
                for field_name in (
                    'type', 'prefix', 'suffix', 'decimal_places', 'show_value',
                    'show_date', 'show_time', 'show_seconds', 'show_if_set',
                    'show_class_name', 'show_symbol', 'visible',
                    'is_user', 'user_can_add', 'user_can_remove',
                    'icon_file', 'semantic_type', 'merge_behaviour', 'paste_behaviour',
                ):
                    val = getattr(ac, field_name, None)
                    if val is not None:
                        d[field_name] = val
                # Pass Font dataclass directly — builder uses _font_overrides_from_dc()
                d['font'] = ac.font
                att_class_config[ac.name] = d

        # ── Geo-map: auto-register semantic properties (before resolution) ─
        _geo_needs_latlon = False
        if s.extra_cfg.geo_map and s.extra_cfg.geo_map.attribute_name:
            gm = s.extra_cfg.geo_map
            _geo_mode_pre = gm.mode or 'both'
            if _geo_mode_pre in ('latlon', 'both'):
                _geo_needs_latlon = True
                # i2 standard property GUIDs (LATITUDE_GUID, LONGITUDE_GUID,
                # GRID_REFERENCE_GUID) live in anxwritter/guids.py — required
                # for ANB's Esri Maps subsystem to recognise these attributes.
                # Register Latitude/Longitude attribute classes on builder
                builder._att_class_id('Latitude', 'AttNumber')
                builder._att_class_id('Longitude', 'AttNumber')
                # Auto-register semantic properties if not already provided
                _has_gr = any(sp.name == 'Grid Reference' for sp in self._semantic_properties)
                _has_lat = any(sp.name == 'Latitude' for sp in self._semantic_properties)
                _has_lon = any(sp.name == 'Longitude' for sp in self._semantic_properties)
                if not _has_gr:
                    self.add_semantic_property(
                        name='Grid Reference', guid=GRID_REFERENCE_GUID,
                        base_property='Abstract Number',
                    )
                if not _has_lat:
                    self.add_semantic_property(
                        name='Latitude', guid=LATITUDE_GUID,
                        base_property='Grid Reference',
                    )
                if not _has_lon:
                    self.add_semantic_property(
                        name='Longitude', guid=LONGITUDE_GUID,
                        base_property='Grid Reference',
                    )
                # Set semantic_type on the attribute class configs
                if 'Latitude' not in att_class_config:
                    att_class_config['Latitude'] = {}
                att_class_config['Latitude']['semantic_type'] = LATITUDE_GUID
                att_class_config['Latitude']['type'] = 'number'
                if 'Longitude' not in att_class_config:
                    att_class_config['Longitude'] = {}
                att_class_config['Longitude']['semantic_type'] = LONGITUDE_GUID
                att_class_config['Longitude']['type'] = 'number'

        # ── Semantic type resolution (MUST be before entity/link loops) ───
        with timer.phase("Semantic type resolution"):
            semantic_config, _entity_semantic_guids, _link_semantic_guids = \
                self._resolve_semantic_types(builder, att_class_config)

        # ── Auto-color pre-computation ───────────────────────────────────
        with timer.phase("Auto-color precompute"):
            _auto_colors: Dict[str, Tuple[int, int]] = {}
            if s.extra_cfg.entity_auto_color:
                _auto_colors = compute_auto_colors(self._entities)

        # ── Entity color map for link_match_entity_color ─────────────────
        with timer.phase("Init maps/queues"):
            _entity_color_map: Dict[str, int] = {}
            _theme_line_auto: List[Tuple[str, Optional[int]]] = []
            st_config = list(self.source_types)

            # ── Grade sentinel / default resolution ─────────────────────
            def _resolve_grade(gc: GradeCollection) -> Tuple[List[str], Optional[int]]:
                if not gc.items and gc.default is None:
                    return ([], None)
                items = list(gc.items)
                if gc.default is None:
                    items.append('-')
                    return (items, len(items) - 1)
                # default must be in items (validated earlier)
                return (items, items.index(gc.default))

            gc1_config, _gc1_default_idx = _resolve_grade(self.grades_one)
            gc2_config, _gc2_default_idx = _resolve_grade(self.grades_two)
            gc3_config, _gc3_default_idx = _resolve_grade(self.grades_three)

            _grade_params = [
                ('grade_one', _gc1_default_idx),
                ('grade_two', _gc2_default_idx),
                ('grade_three', _gc3_default_idx),
            ]
            _grade_resolve_specs = [
                ('grade_one', gc1_config),
                ('grade_two', gc2_config),
                ('grade_three', gc3_config),
            ]

            # ── Strength fallback resolution ────────────────────────────
            _user_defined_strengths = any(
                st.name != 'Default' for st in self.strengths.items
            )
            if _user_defined_strengths:
                _strength_fallback = self.strengths.default or '-'
                builder.replace_default_strength(_strength_fallback)
            else:
                _strength_fallback = None

        # ── Geo-map: match entities and compute positions ────────────────
        _geo_matched: Dict[str, List[Tuple[str, float, float]]] = {}
        _geo_mode: Optional[str] = None
        _geo_bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)
        if s.extra_cfg.geo_map and s.extra_cfg.geo_map.attribute_name:
            with timer.phase("Geo-map resolve"):
                gm = s.extra_cfg.geo_map
                _geo_mode = gm.mode or 'both'
                _geo_data = resolve_geo_data(gm)
                if _geo_data:
                    _geo_fold = gm.accent_insensitive if gm.accent_insensitive is not None else True
                    _geo_matched = match_geo_entities(
                        self._entities, _geo_data, gm.attribute_name,
                        accent_insensitive=_geo_fold,
                    )
                    # Set positions for 'position' and 'both' modes
                    if _geo_mode in ('position', 'both') and _geo_matched:
                        _geo_bbox = compute_geo_positions(
                            _geo_matched,
                            builder._positions,
                            width=gm.width or 3000,
                            height=gm.height or 2000,
                            spread_radius=gm.spread_radius or 0,
                        )

        # ── Loose card resolution (side-table — no user-object mutation) ──
        _entity_id_set = {e.id for e in self._entities if e.id}
        _link_id_set = {lk.link_id for lk in self._links if lk.link_id}
        _loose_entity_cards: Dict[str, List[Card]] = {}
        _loose_link_cards: Dict[str, List[Card]] = {}
        card_errors = []
        for card in self._loose_cards:
            if card.entity_id:
                if card.entity_id not in _entity_id_set:
                    card_errors.append(
                        f"Loose card references unknown entity_id '{card.entity_id}'"
                    )
                else:
                    _loose_entity_cards.setdefault(card.entity_id, []).append(card)
            elif card.link_id:
                if card.link_id not in _link_id_set:
                    card_errors.append(
                        f"Loose card references unknown link_id '{card.link_id}'"
                    )
                else:
                    _loose_link_cards.setdefault(card.link_id, []).append(card)
        if card_errors:
            raise ANXValidationError(card_errors)

        # ── Resolve all entities (no user-object mutation) ─────────────
        _t0_entities = time.perf_counter()
        resolved_entities = []
        for entity in self._entities:
            if not entity.id:
                errors.append(f"Entity {type(entity).__name__}: missing 'id' — skipped")
                continue
            re = builder.resolve_entity(
                entity,
                extra_cards=_loose_entity_cards.get(entity.id, []),
                semantic_guid=_entity_semantic_guids.get(entity.id),
            )
            if re is None:
                continue  # dedup — already registered
            resolved_entities.append(re)
            entity_registry[re.identity] = (re.ci_id, re.entity_int_id)
        timer.record(f"Entity resolve ({len(self._entities)})", time.perf_counter() - _t0_entities)

        # ── Auto-color transform (on resolved data, no user-object mutation)
        with timer.phase("Auto-color transform"):
            if s.extra_cfg.entity_auto_color:
                apply_auto_colors(resolved_entities, _auto_colors)

        # ── Entity color map (from resolved data) ────────────────────────
        _entity_color_map = build_entity_color_map(resolved_entities)

        # ── Positions and ThemeLine handling (from original entity objects)
        for entity in self._entities:
            eid = entity.id
            if not eid or eid not in entity_registry:
                continue
            if entity.x is not None and entity.y is not None:
                try:
                    builder._positions[eid] = (int(entity.x), int(entity.y))
                except (ValueError, TypeError):
                    pass
            if isinstance(entity, ThemeLine):
                has_x = entity.x is not None
                has_y = entity.y is not None
                if has_y and not has_x:
                    if eid not in builder._positions:
                        builder._positions[eid] = (0, int(entity.y))
                elif not has_y:
                    _tl_x = int(entity.x) if has_x else None
                    _theme_line_auto.append((eid, _tl_x))

        # ── Apply grade defaults to resolved entities ──────────────────
        with timer.phase("Grade defaults (entities)"):
            resolve_grade_names(resolved_entities, _grade_resolve_specs)
            apply_grade_defaults(resolved_entities, _grade_params)

        # ── Inject Latitude/Longitude attributes (geo_map latlon/both) ──
        if _geo_matched and _geo_mode in ('latlon', 'both'):
            with timer.phase("Geo-map inject attributes"):
                _lat_ref = builder._att_classes.get('Latitude', (None,))[0]
                _lon_ref = builder._att_classes.get('Longitude', (None,))[0]
                if _lat_ref and _lon_ref:
                    inject_geo_attributes(
                        resolved_entities, _geo_matched, _lat_ref, _lon_ref,
                    )

        # ── Store resolved entities for lazy emit in build() ────────────
        builder._resolved_items.extend(resolved_entities)

        # ── Link offset pre-computation ───────────────────────────────────
        with timer.phase("Link offset precompute"):
            link_spacing = s.extra_cfg.link_arc_offset if s.extra_cfg.link_arc_offset is not None else 20
            _auto_offsets = compute_link_offsets(self._links, link_spacing)

        # ── Resolve all links + apply transforms (no user-object mutation)
        _t0_links = time.perf_counter()
        resolved_links = []
        for i, link in enumerate(self._links):
            if not link.from_id or not link.to_id:
                errors.append(f"Link {i}: missing 'from_id' or 'to_id' — skipped")
                continue
            if link.from_id == link.to_id:
                errors.append(f"Link {i}: self-loop — skipped")
                continue

            from_info = entity_registry.get(link.from_id)
            to_info = entity_registry.get(link.to_id)
            if not from_info:
                errors.append(f"Link {i}: entity '{link.from_id}' not found (from_id) — skipped")
            if not to_info:
                errors.append(f"Link {i}: entity '{link.to_id}' not found (to_id) — skipped")
            if not from_info or not to_info:
                continue

            rl = builder.resolve_link(
                link,
                extra_cards=_loose_link_cards.get(link.link_id or '', []),
                semantic_guid=_link_semantic_guids.get(i),
            )

            # link_match_entity_color — transform on resolved data, not original
            if link.line_color is None and s.extra_cfg.link_match_entity_color and link.to_id in _entity_color_map:
                rl.line_color = _entity_color_map[link.to_id]

            # Auto offset — only when original link had no explicit offset
            if link.offset is None:
                rl.offset = _auto_offsets.get(i, 0)

            resolved_links.append(rl)
        timer.record(f"Link resolve ({len(self._links)})", time.perf_counter() - _t0_links)

        # ── Apply grade defaults to resolved links ─────────────────────
        with timer.phase("Grade defaults (links)"):
            resolve_grade_names(resolved_links, _grade_resolve_specs)
            apply_grade_defaults(resolved_links, _grade_params)

        # ── Store resolved links for lazy emit in build() ───────────────
        builder._resolved_items.extend(resolved_links)

        # ── Build configs ─────────────────────────────────────────────────
        with timer.phase("Build configs"):
            # att_class_config already built above (before semantic resolution)
            strength_config: Dict[str, str] = {}
            for st in self.strengths.items:
                if st.name:
                    strength_config[st.name] = _enum_val(st.dot_style)
            if _user_defined_strengths:
                strength_config.pop('Default', None)

            datetime_format_config: List[Dict[str, str]] = []
            for dtf in self._datetime_formats:
                if dtf.name:
                    d: Dict[str, str] = {'name': dtf.name}
                    if dtf.format:
                        d['format'] = dtf.format
                    datetime_format_config.append(d)

        with timer.phase("ThemeLine Y-offsets"):
            compute_theme_line_y_offsets(_theme_line_auto, builder._positions, spacing=30)

        with timer.phase("Legend items"):
            legend_items = []
            for li in self._legend_items:
                d: Dict[str, Any] = {}
                for field_name in (
                    'name', 'item_type', 'color', 'line_width', 'dash_style',
                    'arrows', 'image_name', 'shade_color',
                ):
                    val = getattr(li, field_name, None)
                    if val is not None:
                        if field_name in ('color', 'shade_color'):
                            if isinstance(val, str):
                                val = color_to_colorref(val)
                            elif isinstance(val, float):
                                val = int(val)
                        d[field_name] = val
                # Pass Font dataclass directly — builder uses _font_overrides_from_dc()
                d['font'] = li.font
                legend_items.append(d)

        # Build palette dicts for the builder
        palette_dicts: Optional[List[Dict[str, Any]]] = None
        if self._palettes:
            palette_dicts = []
            for pal in self._palettes:
                pd: Dict[str, Any] = {'name': pal.name, 'locked': pal.locked}
                if pal.entity_types:
                    pd['entity_types'] = list(pal.entity_types)
                if pal.link_types:
                    pd['link_types'] = list(pal.link_types)
                if pal.attribute_classes:
                    pd['attribute_classes'] = list(pal.attribute_classes)
                if pal.attribute_entries:
                    pd['attribute_entries'] = [
                        {'name': ae.name, 'value': ae.value}
                        for ae in pal.attribute_entries
                    ]
                palette_dicts.append(pd)

        # ── Assemble summary config ────────────────────────────────────
        _SUMMARY_FIELD_NAMES = (
            'title', 'subject', 'keywords', 'category', 'comments',
            'author', 'template',
        )
        _ORIGIN_FIELD_NAMES = (
            'created', 'edit_time', 'last_print', 'last_save', 'revision',
        )
        summary_fields: Dict[str, str] = {}
        for fname in _SUMMARY_FIELD_NAMES:
            v = getattr(s.summary, fname, None)
            if v is not None and str(v).strip():
                summary_fields[fname] = str(v)
        origin_fields: Dict[str, Any] = {}
        for fname in _ORIGIN_FIELD_NAMES:
            v = getattr(s.summary, fname, None)
            if v is not None:
                origin_fields[fname] = v
        custom_props = list(s.summary.custom_properties or [])
        summary_config = None
        if summary_fields or origin_fields or custom_props:
            summary_config = {
                'fields': summary_fields,
                'origin': origin_fields,
                'custom_properties': custom_props,
            }

        # ── Geo-map layout center offset ─────────────────────────────────
        _layout_center = (0, 0)
        if _geo_bbox != (0, 0, 0, 0):
            # Place unmatched entities below the geo-positioned bounding box
            _layout_center = (
                (_geo_bbox[0] + _geo_bbox[2]) // 2,  # center X of geo area
                _geo_bbox[3] + 200,                    # below geo area + margin
            )

        with timer.phase("builder.build()"):
            xml_str = builder.build(
                s,
                att_class_config=att_class_config,
                strength_config=strength_config,
                gc1=gc1_config,
                gc2=gc2_config,
                gc3=gc3_config,
                source_types=st_config,
                legend_items=legend_items,
                palettes=palette_dicts,
                summary_config=summary_config,
                datetime_format_config=datetime_format_config,
                semantic_config=semantic_config,
                layout_center=_layout_center,
            )

        timer.summary(
            extra=f"Entities: {len(self._entities)}, Links: {len(self._links)}",
            sub_timings=[("builder.build()", builder._build_timer)],
        )
        return xml_str, errors
