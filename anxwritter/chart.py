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
import yaml
import os
import tempfile
import time
from datetime import datetime as _datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

from loguru import logger

from .builder import ANXBuilder
from ._config_layering import (
    _ConfigLayeringMixin,
    _CASCADE_MODE_TO_TRIPLE,
    _extract_cascade_meta,
)
from .colors import color_to_colorref
from .entities import _BaseEntity, Icon, Box, Circle, ThemeLine, EventFrame, TextBlock, Label
from .enums import DotStyle, Representation
from .errors import ANXValidationError, ErrorType
from ._i2_interop import LATITUDE_GUID, LONGITUDE_GUID, GRID_REFERENCE_GUID
from .models import (
    Card, Link, AttributeClass,
    DisplayAttribute, DisplayLabel, Strength, LegendItem,
    EntityType, LinkType,
    Palette, PaletteAttributeEntry, DateTimeFormat,
    SemanticEntity, SemanticLink, SemanticProperty,
    GradeCollection, StrengthCollection,
    Settings, Font, Frame, Show, TimeZone, CustomProperty,
    Validator, IconMapCfg, IconRule,
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
    apply_icon_map,
    apply_link_categorical,
    apply_link_intensity,
    generate_styling_legend,
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


# ── Main class ────────────────────────────────────────────────────────────────

class ANXChart(_ConfigLayeringMixin):
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
        # Embedded custom icons (1.19.0): bare name -> {emitted, data, datalength}
        self._custom_entity_icons: Dict[str, dict] = {}
        self._custom_attribute_icons: Dict[str, dict] = {}
        # Custom-icon layering locks (1.20.0): (section, name) -> locked entry.
        # Set by a lock-mode config layer; a later layer changing it → locked_override.
        self._custom_icon_locked: Dict[Tuple[str, str], dict] = {}
        self._palettes: List[Palette] = []
        self._datetime_formats: List[DateTimeFormat] = []
        self._semantic_entities: List['SemanticEntity'] = []
        self._semantic_links: List['SemanticLink'] = []
        self._semantic_properties: List['SemanticProperty'] = []
        self.grades_one: GradeCollection = GradeCollection()
        self.grades_two: GradeCollection = GradeCollection()
        self.grades_three: GradeCollection = GradeCollection()
        self.source_types: List[str] = []
        # Top-level value-enforcement rules (1.17.0). Identity is the
        # synthesized key (`E::Person::CPF` / `L::Transfer::Currency`)
        # computed from `entity_type`/`link_type` + `attribute`. Layering
        # uses `_merge_keyed_section` with an `identity_fn` so the key never
        # needs to live as a field on the dataclass.
        self._validators: List[Validator] = []

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

        # Config-vs-config leaf locks (set only by lock=True layers). Keyed at
        # LEAF granularity: (section, identity_or_None, dotted_leaf) -> value.
        #   named/synth: ('attribute_classes', 'Person', 'font.bold') -> True
        #   settings:    ('settings', None, 'view.time_bar') -> True
        #   grades:      ('grades_one', None, 'default') / (..., 'item:High')
        # A later config layer changing a locked leaf gets a locked_override
        # error and the locked value is preserved (fail-safe).
        self._config_locked_leaves: Dict[tuple, Any] = {}

        # Source provenance — maps config entries back to the layer that set them.
        # Populated by `_apply_config` when a `source_name` is supplied (explicit
        # kwarg, or auto-derived from the path in `apply_config_file`).
        # `_config_sources[(section, name)]` → source_name for named-upsert
        # sections (entity_types, link_types, attribute_classes, strengths.items,
        # datetime_formats, semantic_*). `_config_section_sources[section]` →
        # source_name for list-only sections (grades_one/two/three, source_types).
        # Consumed by validators to enrich error dicts with an optional `source`
        # key; consulted by `ANXValidationError.__str__` for the message suffix.
        self._config_sources: Dict[tuple, str] = {}
        self._config_section_sources: Dict[str, str] = {}

        if config_file:
            self.apply_config_file(config_file)
        elif config:
            self.apply_config(config)

    def _apply_data(self, data: dict) -> None:
        """Apply a full data dict (config sections + entities + links).

        Config sections are processed via ``_apply_config(is_config=False)``
        (conflict detection active when a config was previously applied).
        Entities and links are parsed and added to the chart.

        A top-level ``cascade`` block is silently stripped — it's an
        apply-time layering directive (handled by :meth:`apply_config`) and
        has no meaning when constructing a chart in one shot via
        :meth:`from_dict` / :meth:`from_yaml` / :meth:`from_json` etc.
        """
        if isinstance(data, dict) and 'cascade' in data:
            # Validate the block's shape so a malformed cascade still raises
            # on the construction path (catches typos early), then drop it.
            _extract_cascade_meta(data)
            data = {k: v for k, v in data.items() if k != 'cascade'}

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

    def apply_config(
        self,
        data: dict,
        *,
        operation: Optional[str] = None,
        wipe_previous: Optional[bool] = None,
        lock: Optional[bool] = None,
        source_name: Optional[str] = None,
    ) -> None:
        """Apply a config dict to this chart (one config layer).

        Only config sections are applied (settings, entity_types, link_types,
        attribute_classes, strengths, datetime_formats, semantic_*, palettes,
        legend_items, grades, source_types). ``entities`` / ``links`` keys are
        silently ignored.

        Precedence for layering knobs: an explicit kwarg here overrides the
        file's top-level ``cascade.mode`` block; if neither is set, the
        layer defaults to plain merge. Pass ``None`` (the default) for any
        knob you want the file's ``cascade.mode`` to drive.

        Layering rules (``operation='merge'``, the default):

        - ``settings``: deep merge per leaf — only leaves the layer sets
          overwrite.
        - ``entity_types``, ``link_types``, ``attribute_classes``,
          ``datetime_formats``, ``semantic_*``, ``strengths.items``,
          ``extra_cfg.display_attribute`` / ``display_label``: **field-merge**
          by identity (``name`` / ``key``) — a later layer's declared fields
          merge into the same-identity entry; omitted fields are retained; new
          identities are appended.
        - ``strengths.default``, ``grades_*.default``: later wins if non-None.
        - ``source_types``, ``grades_*.items``: append with case-sensitive
          exact-text dedup.
        - ``legend_items``, ``palettes``: append (no natural key).

        ``operation='delete'`` subtracts by shape (the mirror of merge): a key
        with a null/empty value removes the whole section/entry; a list entry
        with only its identity removes that entry; an entry naming fields
        (which must be ``null``) unsets those fields. A non-null value on a
        non-identity field in a delete layer is a ``delete_contract`` error.
        Deleting an absent target is a no-op.

        ``wipe_previous=True`` (merge only) clears each section the layer
        mentions before merging — the "narrow the list" case.

        ``lock=True`` (merge only) freezes exactly the leaves this layer
        declares. A later config layer that changes a locked leaf records a
        ``locked_override`` error and the locked value is preserved. Surfaced
        through :meth:`validate` like any other conflict.

        ``operation='delete'`` combined with ``lock`` or ``wipe_previous`` is a
        ``ValueError`` (contradictory).

        When *source_name* is supplied, every entry this layer contributes is
        tagged so :meth:`validate` errors carry an optional ``source`` key.
        ``apply_config_file`` auto-derives it from the file's basename.

        No validation runs at load time. Call :meth:`validate` afterwards.
        """
        cleaned, mode = _extract_cascade_meta(data) if data else (data, None)
        cs_op, cs_wipe, cs_lock = (
            _CASCADE_MODE_TO_TRIPLE[mode] if mode
            else ('merge', False, False)
        )
        self._apply_config(
            cleaned, is_config=True,
            operation=cs_op if operation is None else operation,
            wipe_previous=cs_wipe if wipe_previous is None else wipe_previous,
            lock=cs_lock if lock is None else lock,
            source_name=source_name,
        )

    def apply_config_file(
        self,
        path: Union[str, Path],
        *,
        operation: Optional[str] = None,
        wipe_previous: Optional[bool] = None,
        lock: Optional[bool] = None,
        source_name: Optional[str] = None,
    ) -> None:
        """Load a config file (JSON or YAML) and apply it as one config layer.

        See :meth:`apply_config` for the layering rules and the meaning of
        *operation* / *wipe_previous* / *lock* (including precedence vs the
        file's ``cascade.mode``). Call :meth:`validate` after loading to
        catch schema errors before feeding the chart any data.

        *source_name* defaults to the file's basename (``Path(path).name``).
        """
        data = self._load_file(path)
        if source_name is None:
            source_name = Path(path).name
        self.apply_config(
            data, operation=operation, wipe_previous=wipe_previous,
            lock=lock, source_name=source_name,
        )

    @classmethod
    def from_config(
        cls,
        source: str,
        *,
        operation: Optional[str] = None,
        wipe_previous: Optional[bool] = None,
        lock: Optional[bool] = None,
        source_name: Optional[str] = None,
    ) -> "ANXChart":
        """Create an ANXChart pre-loaded with config from a JSON or YAML string.

        Tries JSON first; falls back to YAML if JSON parsing fails.

        See :meth:`apply_config` for *operation* / *wipe_previous* / *lock*
        precedence (file ``cascade.mode`` is honored when the kwarg is None)
        and *source_name*.
        """
        try:
            data = json.loads(source)
        except (json.JSONDecodeError, ValueError):
            data = yaml.safe_load(source)
        chart = cls()
        chart.apply_config(
            data, operation=operation, wipe_previous=wipe_previous,
            lock=lock, source_name=source_name,
        )
        return chart

    @classmethod
    def from_config_file(
        cls,
        path: Union[str, Path],
        *,
        operation: Optional[str] = None,
        wipe_previous: Optional[bool] = None,
        lock: Optional[bool] = None,
        source_name: Optional[str] = None,
    ) -> "ANXChart":
        """Create an ANXChart pre-loaded with config from a JSON or YAML file.

        Format detected by extension (.yaml/.yml -> YAML, else JSON).

        See :meth:`apply_config` for *operation* / *wipe_previous* / *lock*
        precedence (file ``cascade.mode`` is honored when the kwarg is None)
        and *source_name* (which defaults to ``Path(path).name``).
        """
        chart = cls()
        chart.apply_config_file(
            path, operation=operation, wipe_previous=wipe_previous,
            lock=lock, source_name=source_name,
        )
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

        def _anchor(value: str) -> str:
            """Anchor a relative filesystem path; leave data: URIs / absolute alone."""
            if not isinstance(value, str) or not value or value.startswith('data:'):
                return value
            p = Path(value)
            return value if p.is_absolute() else str((base_dir / p).resolve())

        # custom_entity_icons[].image / custom_attribute_icons[].image
        for section in ('custom_entity_icons', 'custom_attribute_icons'):
            for entry in (data.get(section) or []):
                if isinstance(entry, dict) and 'image' in entry:
                    entry['image'] = _anchor(entry['image'])

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
            result['palettes'] = [
                self._palette_to_dict(pal, full=False) for pal in self._palettes
            ]

        # Validators (1.17.0). Excludes the private _compiled_pattern attr
        # because it isn't a dataclass field.
        if self._validators:
            result['validators'] = [
                self._dc_to_clean_dict(v) for v in self._validators
            ]

        # Custom icons (1.19.0) — export the converted BMP as a data: URI so the
        # config round-trips (re-import sees a BMP and embeds it verbatim).
        import base64 as _b64
        import zlib as _zlib
        from .custom_icons import EMITTED_PREFIX as _DEFAULT_ICON_PREFIX
        for section, registry in (('custom_entity_icons', self._custom_entity_icons),
                                  ('custom_attribute_icons', self._custom_attribute_icons)):
            if registry:
                rows = []
                for name, e in registry.items():
                    raw_bmp = _zlib.decompress(_b64.b64decode(e['data']))
                    row = {
                        'name': name,
                        'image': 'data:image/bmp;base64,' + _b64.b64encode(raw_bmp).decode(),
                    }
                    if e['prefix'] != _DEFAULT_ICON_PREFIX:
                        row['prefix'] = e['prefix']
                    rows.append(row)
                result[section] = rows

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
        elif isinstance(item, DisplayAttribute):
            self.settings.extra_cfg.display_attribute.append(item)
        elif isinstance(item, DisplayLabel):
            self.settings.extra_cfg.display_label.append(item)
        elif isinstance(item, Validator):
            self.add_validator(item)
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

    def _register(self, collection, cls, name_or_obj, kwargs, *,
                  upsert=True, coerce=None) -> None:
        """Accept an existing ``cls`` instance or build one from kwargs, then add
        it to ``collection``.

        ``name_or_obj`` is either a ready ``cls`` instance or the positional
        ``name`` shortcut. ``upsert=True`` replaces a same-name entry (named
        registries); otherwise the object is appended (legend / palette).
        ``coerce`` is an optional callback that adjusts the kwargs dict before
        construction.
        """
        if isinstance(name_or_obj, cls):
            obj = name_or_obj
        else:
            if name_or_obj is not None:
                kwargs['name'] = name_or_obj
            if coerce is not None:
                coerce(kwargs)
            obj = cls(**kwargs)
        if upsert:
            self._upsert_by_name(collection, obj)
        else:
            collection.append(obj)

    @staticmethod
    def _coerce_palette_kwargs(kwargs: dict) -> None:
        """Convert ``attribute_entries`` dicts to ``PaletteAttributeEntry`` in place."""
        ae = kwargs.get('attribute_entries')
        if ae and isinstance(ae, list):
            kwargs['attribute_entries'] = [
                PaletteAttributeEntry(**e) if isinstance(e, dict) else e
                for e in ae
            ]

    def add_attribute_class(self, name_or_obj=None, **kwargs) -> None:
        """Add or update an AttributeClass. Later calls with the same
        ``name`` replace the earlier entry."""
        self._register(self._attribute_classes, AttributeClass, name_or_obj, kwargs)

    def add_strength(self, name_or_obj=None, **kwargs) -> None:
        """Add or update a Strength. Pass a Strength object or keyword args.

        If a Strength with the same name already exists (e.g. the pre-populated
        ``'Default'``), it is replaced rather than duplicated.
        """
        self._register(self.strengths.items, Strength, name_or_obj, kwargs)

    def add_datetime_format(self, name_or_obj=None, **kwargs) -> None:
        """Add or update a DateTimeFormat. Pass a DateTimeFormat object or keyword args.

        If a DateTimeFormat with the same name already exists, it is replaced
        rather than duplicated.
        """
        self._register(self._datetime_formats, DateTimeFormat, name_or_obj, kwargs)

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
        self._register(self._legend_items, LegendItem, name_or_obj, kwargs, upsert=False)

    def add_display_attribute(self, obj=None, **kwargs) -> None:
        """Add a :class:`DisplayAttribute` to ``extra_cfg.display_attribute``.

        Pass a ``DisplayAttribute`` instance or keyword args matching its
        fields (``key``, ``attribute_name``, ``kind``, ``type``, ``template``,
        ``decimal_separator``, ``thousand_separator``, ``sources``,
        ``attribute_class``). Multiple entries can be added; they are appended
        in order. Validation runs at :meth:`validate` time.
        """
        if isinstance(obj, DisplayAttribute):
            self.settings.extra_cfg.display_attribute.append(obj)
        else:
            self.settings.extra_cfg.display_attribute.append(
                DisplayAttribute(**kwargs)
            )

    def add_display_label(self, obj=None, **kwargs) -> None:
        """Add a :class:`DisplayLabel` to ``extra_cfg.display_label``.

        Pass a ``DisplayLabel`` instance or keyword args matching its fields
        (``key``, ``kind``, ``type``, ``template``, ``decimal_separator``,
        ``thousand_separator``, ``sources``, ``override_existing``). Multiple
        entries can be added; they are appended in order. Validation runs at
        :meth:`validate` time.
        """
        if isinstance(obj, DisplayLabel):
            self.settings.extra_cfg.display_label.append(obj)
        else:
            self.settings.extra_cfg.display_label.append(
                DisplayLabel(**kwargs)
            )

    def add_icon_map_rule(self, obj=None, **kwargs) -> None:
        """Add an :class:`IconRule` to ``extra_cfg.icon_map.rules``.

        Pass an ``IconRule`` instance or keyword args matching its fields
        (``match``, ``attribute_name``, ``type``, ``mapping``, ``default``,
        ``default_when_absent``, ``strict_match``). Creates the
        :class:`IconMapCfg` container on first use. Rules are appended in order;
        precedence is by tier (id > typed-attribute > untyped-attribute,
        last-wins within a tier). Validation runs at :meth:`validate` time.
        """
        rule = obj if isinstance(obj, IconRule) else IconRule(**kwargs)
        if self.settings.extra_cfg.icon_map is None:
            self.settings.extra_cfg.icon_map = IconMapCfg()
        self.settings.extra_cfg.icon_map.rules.append(rule)

    def add_entity_type(self, name_or_obj=None, **kwargs) -> None:
        """Add or update an EntityType. Later calls with the same ``name``
        replace the earlier entry."""
        self._register(self._entity_types, EntityType, name_or_obj, kwargs)

    def add_link_type(self, name_or_obj=None, **kwargs) -> None:
        """Add or update a LinkType. Later calls with the same ``name``
        replace the earlier entry."""
        self._register(self._link_types, LinkType, name_or_obj, kwargs)

    def add_semantic_entity(self, name_or_obj=None, **kwargs) -> None:
        """Add or update a custom entity semantic type. Later calls with the
        same ``name`` replace the earlier entry."""
        self._register(self._semantic_entities, SemanticEntity, name_or_obj, kwargs)

    def add_semantic_link(self, name_or_obj=None, **kwargs) -> None:
        """Add or update a custom link semantic type. Later calls with the
        same ``name`` replace the earlier entry."""
        self._register(self._semantic_links, SemanticLink, name_or_obj, kwargs)

    def add_semantic_property(self, name_or_obj=None, **kwargs) -> None:
        """Add or update a custom property semantic type. Later calls with
        the same ``name`` replace the earlier entry."""
        self._register(self._semantic_properties, SemanticProperty, name_or_obj, kwargs)

    def add_palette(self, name_or_obj=None, **kwargs) -> None:
        """Add a Palette. Pass a Palette object or keyword args.

        When keyword args include ``attribute_entries`` as a list of dicts,
        each dict is converted to a ``PaletteAttributeEntry``.
        """
        self._register(self._palettes, Palette, name_or_obj, kwargs,
                       upsert=False, coerce=self._coerce_palette_kwargs)

    def add_validator(self, obj=None, **kwargs) -> None:
        """Add or update a :class:`Validator` (1.17.0).

        Pass a ``Validator`` instance or keyword args matching its fields
        (``entity_type`` | ``link_type``, ``attribute``, ``pattern`` |
        ``allowed_values``, ``description``). Upsert is by the synthesized
        key — a later call with the same ``(entity_type|link_type,
        attribute)`` scope replaces the earlier entry. Bad regex / both
        shapes set raise ``ValueError`` at construction; missing or
        ambiguous scope is caught by :meth:`validate`.
        """
        if isinstance(obj, Validator):
            v = obj
        else:
            v = Validator(**kwargs)
        new_key = v.key
        if new_key is not None:
            for i, existing in enumerate(self._validators):
                if existing.key == new_key:
                    self._validators[i] = v
                    return
        self._validators.append(v)

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
            validate_geo_map,
            validate_icon_map,
            validate_styling,
            validate_display_attribute,
            validate_display_label,
            validate_id_patterns,
            validate_required_attributes,
            validate_ac_value_rules,
            validate_validator_rules,
            validate_validators_config,
            validate_enforce_descriptions,
            validate_custom_icons_include,
        )

        errors: List[Dict[str, Any]] = []

        # Prepend config conflict errors (collected during _apply_config)
        if self._config_conflicts:
            errors.extend(self._config_conflicts)

        # Build per-section name→source maps for source-aware validators.
        # Empty dicts when no `source_name` was ever supplied — validators
        # then skip the optional `source` key entirely (existing behaviour).
        def _src_map(section: str) -> Dict[str, str]:
            return {
                name: src
                for (sec, name), src in self._config_sources.items()
                if sec == section
            }
        et_sources = _src_map('entity_types')
        lt_sources = _src_map('link_types')
        ac_sources = _src_map('attribute_classes')
        st_sources = _src_map('strengths')
        dtf_sources = _src_map('datetime_formats')

        # Validate strength collection (default + duplicates)
        errors.extend(validate_strength_collection(self.strengths, st_sources or None))

        # Validate grade collections (defaults exist in items)
        errors.extend(validate_grade_collections(
            self.grades_one, self.grades_two, self.grades_three,
            section_sources=self._config_section_sources or None,
        ))

        # Validate datetime formats (duplicates, length limits)
        dtf_errors, dtf_names = validate_datetime_formats(
            self._datetime_formats, dtf_sources or None
        )
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
        et_errors, et_names = validate_entity_types(
            self._entity_types, et_sources or None
        )
        errors.extend(et_errors)

        # Validate link types (returns name->location map for palette validation)
        lt_errors, lt_names = validate_link_types(
            self._link_types, lt_sources or None
        )
        errors.extend(lt_errors)

        # Validate attribute classes (returns name->location map for palette validation)
        ac_errors, ac_names = validate_attribute_classes(
            self._attribute_classes, attr_types, ac_sources or None
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
        errors.extend(validate_geo_map(
            self.settings.extra_cfg.geo_map, self._entities
        ))

        # Validate icon_map configuration
        errors.extend(validate_icon_map(
            self.settings.extra_cfg.icon_map,
            self._entities,
            set(et_names.keys()),
        ))

        # Validate styling (extra_cfg.styling.links.{intensity,categorical})
        errors.extend(validate_styling(
            self.settings.extra_cfg.styling,
            self._links,
            strength_names,
        ))

        # Validate the display synthesizers (extra_cfg.display_attribute /
        # display_label).
        et_name_set = set(et_names.keys())
        lt_name_set = set(lt_names.keys())
        errors.extend(validate_display_attribute(
            self.settings.extra_cfg.display_attribute,
            self._attribute_classes,
            self._entities,
            self._links,
            ac_names,
            et_name_set,
            lt_name_set,
        ))
        errors.extend(validate_display_label(
            self.settings.extra_cfg.display_label,
            self._attribute_classes,
            self._entities,
            self._links,
            ac_names,
            et_name_set,
            lt_name_set,
        ))

        # ── Value enforcement (1.17.0) — runs after AC + display synthesizers
        # so synthesized AC values participate in pattern checks.
        validator_sources = _src_map('validators')

        errors.extend(validate_validators_config(
            self._validators, et_names, lt_names, validator_sources or None,
        ))
        errors.extend(validate_enforce_descriptions(
            self._entity_types, self._link_types, self._attribute_classes,
            et_sources or None, lt_sources or None, ac_sources or None,
        ))
        errors.extend(validate_id_patterns(
            self._entities, self._links,
            self._entity_types, self._link_types,
            et_sources or None, lt_sources or None,
        ))
        errors.extend(validate_required_attributes(
            self._entities, self._links,
            self._entity_types, self._link_types,
            et_sources or None, lt_sources or None,
        ))
        errors.extend(validate_ac_value_rules(
            self._entities, self._links,
            self._attribute_classes,
            ac_sources or None,
        ))
        errors.extend(validate_validator_rules(
            self._entities, self._links,
            self._validators,
            validator_sources or None,
        ))

        errors.extend(validate_custom_icons_include(
            self.settings.extra_cfg.custom_icons_include
        ))

        return errors

    # ------------------------------------------------------------------

    def to_anx(self, path: Union[str, Path], *, stream: bool = True,
               compact: bool = True) -> str:
        """Build and write the ANX file.

        The write is **atomic**: content goes to a temp file in the destination
        directory and is then renamed into place with :func:`os.replace`, so a
        failure mid-build never leaves a partial or corrupt ``.anx`` (and any
        existing file is preserved until the new one is complete).

        Args:
            path: Destination path (``str`` or ``pathlib.Path``).
                  ``.anx`` extension added automatically.
            stream: When ``True`` (default), serialize and write incrementally —
                the ``<ChartItem>`` elements are emitted and discarded one at a
                time, so peak memory is roughly the resolved-item set rather than
                the whole element tree plus output string (~0.37x the buffered
                peak; also faster on large charts, negligibly slower on tiny ones).
                ``stream=False`` builds the whole document first. The written
                bytes are identical either way.
            compact: When ``True`` (default), drop indentation (newlines kept) for
                a smaller file — ANB ignores indentation and imports it identically
                to the pretty form. ``compact=False`` writes the indented layout.

        Returns:
            Absolute path of the written file.

        Raises:
            ANXValidationError: If any rows had validation errors.
        """
        validation_errors = self.validate()
        if validation_errors:
            raise ANXValidationError(validation_errors)
        path = str(path)
        if not path.lower().endswith('.anx'):
            path = path + '.anx'
        abspath = os.path.abspath(path)
        directory = os.path.dirname(abspath) or '.'
        os.makedirs(directory, exist_ok=True)
        _t0_write = time.perf_counter()
        # Write to a temp file in the SAME directory, then os.replace() it onto the
        # destination. Same-filesystem os.replace() is a metadata-only atomic rename
        # (no data copy, no extra memory) — it guarantees we never publish a partial
        # .anx if the build raises mid-write, and leaves any existing file untouched
        # until the new content is fully written. It also fully overwrites (no stale
        # trailing bytes when the new content is shorter — an old UTF-16 hazard).
        fd, tmp_path = tempfile.mkstemp(suffix='.anx.tmp', dir=directory)
        try:
            with os.fdopen(fd, 'wb') as fh:
                if stream:
                    for chunk in self._encode_utf16_stream(self._iter_xml(compact=compact)):
                        fh.write(chunk)
                else:
                    xml_content, _build_errors = self._build_xml(compact=compact)
                    fh.write(xml_content.encode('utf-16'))
            os.replace(tmp_path, abspath)
        except BaseException:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise
        logger.debug("File write: {path} ({elapsed:.4f}s)",
                      path=abspath,
                      elapsed=time.perf_counter() - _t0_write)
        return abspath

    def to_xml(self, *, compact: bool = False) -> str:
        """Return the ANX XML as a string without writing a file.

        Args:
            compact: When ``True``, drop indentation (newlines kept). Default
                ``False`` returns the pretty, indented layout — the human-readable
                form for inspection, unchanged across releases.

        Raises:
            ANXValidationError: If any rows had validation errors.
        """
        validation_errors = self.validate()
        if validation_errors:
            raise ANXValidationError(validation_errors)
        xml_content, _build_errors = self._build_xml(compact=compact)
        return xml_content

    def iter_xml(self, *, compact: bool = True) -> Iterator[str]:
        """Yield the ANX XML as string chunks without materializing the whole
        document — lower peak memory for large charts (the ``<ChartItem>`` elements
        are serialized and discarded one at a time).

        Args:
            compact: When ``True`` (default) the output has no indentation (newlines
                kept) — smaller and the recommended form for machine consumption.
                When ``False`` the chunks join to the exact pretty bytes of
                ``to_xml()`` (used for byte-parity testing).

        Raises:
            ANXValidationError: If the chart is invalid. Validation runs up front,
                before any chunk is yielded, so callers fail fast.
        """
        validation_errors = self.validate()
        if validation_errors:
            raise ANXValidationError(validation_errors)
        return self._iter_xml(compact=compact)

    @staticmethod
    def _encode_utf16_stream(chunks: Iterator[str]) -> Iterator[bytes]:
        """Encode str chunks to UTF-16 LE bytes, emitting the BOM exactly once.

        The first chunk is prefixed with the LE BOM (``FF FE``); the rest are plain
        ``utf-16-le`` (no per-chunk BOM). Concatenated, the bytes match
        ``to_xml().encode('utf-16')`` on a little-endian host (what ANB expects).
        """
        first = True
        for chunk in chunks:
            if first:
                yield b"\xff\xfe" + chunk.encode("utf-16-le")
                first = False
            else:
                yield chunk.encode("utf-16-le")

    def iter_anx_bytes(self, *, compact: bool = True) -> Iterator[bytes]:
        """Yield the ``.anx`` as UTF-16 LE bytes (BOM first) without materializing
        the whole document — stream straight into an HTTP response or a file.

        Validates up front (see ``iter_xml``). Concatenated output is identical to
        the bytes ``to_anx()`` writes.
        """
        # iter_xml() validates eagerly here, before any byte is produced.
        return self._encode_utf16_stream(self.iter_xml(compact=compact))

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

    def _add_custom_icon(self, registry, name, image, prefix, printer, kind):
        """Shared body of add_custom_entity_icon / add_custom_attribute_icon.

        Converts the image once and upserts ``{emitted, data, datalength}`` into
        ``registry`` keyed by the bare ``name``. Raises eagerly on bad input.
        """
        from . import custom_icons
        if printer:
            raise NotImplementedError(
                "printer=True (high-resolution print icons) is planned but not "
                "yet shipped; use the default screen icon for now"
            )
        if not name or not str(name).strip():
            raise ValueError("custom icon name is empty")
        emitted = f"{prefix}{name}"
        name_err = custom_icons.validate_icon_name(emitted)
        if name_err:
            raise ValueError(f"custom icon name {emitted!r}: {name_err}")
        bmp = custom_icons.prepare_icon_bmp(image)   # raises CustomIconError on bad image / missing Pillow
        data, dlen = custom_icons.custom_image_payload(bmp)
        registry[str(name)] = {'emitted': emitted, 'prefix': prefix, 'data': data, 'datalength': dlen}

    def add_custom_entity_icon(self, name, image, *, prefix='anxW_', printer=False) -> None:
        """Embed a custom **entity-type** icon under ``name``.

        Reference it by the bare ``name`` from ``EntityType.icon_file`` or a
        per-entity ``Icon.icon``. ``image`` is a path, ``bytes``, a PIL image, or
        a ``data:...;base64,...`` URI. ``prefix`` is prepended to the emitted
        name so it can't collide with an ANB built-in (default ``'anxW_'``; pass
        ``''`` to disable or your own namespace e.g. ``'acme_'``). ``printer`` is
        reserved for high-resolution print icons (not yet shipped).
        """
        self._add_custom_icon(self._custom_entity_icons, name, image, prefix, printer, 'Icon')

    def add_custom_attribute_icon(self, name, image, *, prefix='anxW_', printer=False) -> None:
        """Embed a custom **attribute-class** icon under ``name``.

        Reference it by the bare ``name`` from ``AttributeClass.icon_file``. See
        :meth:`add_custom_entity_icon` for the ``image`` / ``prefix`` / ``printer``
        arguments.
        """
        self._add_custom_icon(self._custom_attribute_icons, name, image, prefix, printer, 'Attribute')

    def apply_icon_catalog(self, catalog, *, include=None) -> None:
        """Merge a baked icon catalog into this chart.

        *catalog* is an :class:`IconCatalog`, a path to an exported catalog/config
        file, or a config-shaped dict. An :class:`IconCatalog` is merged directly
        (already baked). A file/dict is treated as a **config layer** — the Pillow
        gate applies (baked icons only) and a top-level ``cascade.mode`` is
        honored (``merge`` / ``wipe`` / ``lock`` / ``delete``).

        *include* (``'all'`` / ``'referenced'``), when given, sets
        ``settings.extra_cfg.custom_icons_include`` for the whole chart.
        """
        from .custom_icons import IconCatalog, _load_catalog_doc
        if include is not None:
            if include not in ('all', 'referenced'):
                raise ValueError(
                    f"include must be 'all' or 'referenced', got {include!r}"
                )
            self.settings.extra_cfg.custom_icons_include = include

        if isinstance(catalog, IconCatalog):
            for name, e in catalog._entity.items():
                self._custom_entity_icons[str(name)] = dict(e)
            for name, e in catalog._attribute.items():
                self._custom_attribute_icons[str(name)] = dict(e)
            return

        if isinstance(catalog, (str, Path)):
            data = _load_catalog_doc(catalog)
        elif isinstance(catalog, dict):
            data = catalog
        else:
            raise TypeError(
                "catalog must be an IconCatalog, a file path, or a dict"
            )
        cleaned, mode = _extract_cascade_meta(data) if data else (data, None)
        op, wipe, lk = (_CASCADE_MODE_TO_TRIPLE[mode] if mode
                        else ('merge', False, False))
        self._extract_custom_icons(cleaned, is_config=True, operation=op,
                                   wipe_previous=wipe, lock=lk)

    def export_icon_catalog(self, path, *, format='yaml', cascade_mode=None) -> str:
        """Export this chart's registered custom icons as a standalone catalog
        file (baked, Pillow-free to consume). Returns the absolute path."""
        from .custom_icons import IconCatalog
        cat = IconCatalog()
        cat._entity = {n: dict(e) for n, e in self._custom_entity_icons.items()}
        cat._attribute = {n: dict(e) for n, e in self._custom_attribute_icons.items()}
        return cat.export_catalog(path, format=format, cascade_mode=cascade_mode)

    def _write_custom_icon(self, registry, section, name, entry, lock):
        """Lock-aware write of one resolved icon entry into *registry*.

        A later layer changing a leaf locked by an earlier ``lock=True`` layer
        records a ``locked_override`` and the locked value is preserved.
        """
        key = (section, name)
        locked = self._custom_icon_locked.get(key)
        if locked is not None and locked != entry:
            self._config_conflicts.append({
                'type': ErrorType.LOCKED_OVERRIDE.value,
                'section': section, 'name': name,
                'message': (
                    f"cannot change custom icon {section}.{name}: it was locked "
                    f"by an earlier lock layer."
                ),
            })
            return
        registry[str(name)] = entry
        if lock:
            self._custom_icon_locked[key] = entry

    def _extract_custom_icons(self, data, *, is_config=False, operation='merge',
                              wipe_previous=False, lock=False):
        """Apply ``custom_entity_icons`` / ``custom_attribute_icons`` sections
        from a config/data dict and return *data* without them.

        Custom icons are a baked-blob registry, not a field-merge section, so
        they get their own lean layering here (mirroring ``--config`` semantics):

        - ``merge`` (default): upsert by name.
        - ``wipe_previous``: clear the section first.
        - ``lock``: freeze the names this layer declares (later change →
          ``locked_override``).
        - ``operation='delete'``: remove the named entry (no image load).

        **Pillow gate**: a config layer (``is_config=True``) may only carry
        *baked* icons — a ready BMP (``data:image/bmp`` / BMP bytes) or a compiled
        ``data``/``datalength`` payload. A source needing conversion (path / PNG /
        PIL / ``data:image/png``) raises, pointing at :class:`IconCatalog`. The
        data path and the direct ``add_*`` API still convert via Pillow.
        """
        if not isinstance(data, dict):
            return data
        if 'custom_entity_icons' not in data and 'custom_attribute_icons' not in data:
            return data
        from . import custom_icons
        data = dict(data)
        for section, registry in (('custom_entity_icons', self._custom_entity_icons),
                                  ('custom_attribute_icons', self._custom_attribute_icons)):
            entries = data.pop(section, None)
            if entries is None:
                continue
            if wipe_previous:
                registry.clear()
            for entry in (entries or []):
                name = entry['name']
                prefix = entry.get('prefix', custom_icons.EMITTED_PREFIX)

                if operation == 'delete':
                    if (section, str(name)) in self._custom_icon_locked:
                        self._config_conflicts.append({
                            'type': ErrorType.LOCKED_OVERRIDE.value,
                            'section': section, 'name': name,
                            'message': (
                                f"cannot delete custom icon {section}.{name}: "
                                f"locked by an earlier lock layer."
                            ),
                        })
                    else:
                        registry.pop(str(name), None)
                    continue

                emitted = f"{prefix}{name}"
                name_err = custom_icons.validate_icon_name(emitted)
                if name_err:
                    raise ValueError(f"custom icon name {emitted!r}: {name_err}")

                if 'data' in entry and 'datalength' in entry:        # compiled payload
                    resolved = {'emitted': emitted, 'prefix': prefix,
                                'data': entry['data'], 'datalength': entry['datalength']}
                elif 'image' in entry:                                # source image
                    if entry.get('printer'):
                        raise NotImplementedError(
                            "printer=True (high-resolution print icons) is planned "
                            "but not yet shipped"
                        )
                    if is_config and not custom_icons.is_baked(entry['image']):
                        raise ValueError(
                            f"custom icon {name!r} in a config layer must be a ready "
                            f"BMP or a baked catalog entry — Pillow conversion is not "
                            f"allowed in configs. Bake it with IconCatalog(...)."
                            f"export_catalog() or pass a data:image/bmp URI."
                        )
                    bmp = custom_icons.prepare_icon_bmp(entry['image'])
                    bdata, dlen = custom_icons.custom_image_payload(bmp)
                    resolved = {'emitted': emitted, 'prefix': prefix,
                                'data': bdata, 'datalength': dlen}
                else:
                    raise ValueError(
                        f"custom icon entry {name!r} has neither 'data' nor 'image'"
                    )
                self._write_custom_icon(registry, section, name, resolved, lock)
        return data

    def _resolve_icon_ref(self, value, kind):
        """Resolve a bare icon name to its emitted name if registered, else
        pass it through (a built-in / pre-installed name)."""
        if value is None:
            return value
        registry = (self._custom_entity_icons if kind == 'Icon'
                    else self._custom_attribute_icons)
        entry = registry.get(str(value))
        return entry['emitted'] if entry else value

    def _register_static_defs(self, builder: 'ANXBuilder') -> None:
        """Pre-register explicit AttributeClass icons, DateTimeFormats, and
        EntityType / LinkType definitions on the builder (before resolution)."""
        # Push embedded custom icons to the builder + the entity-icon name map
        # (used to resolve per-entity Icon.icon overrides during resolve_entity).
        for entry in self._custom_entity_icons.values():
            builder.add_custom_image(entry['emitted'], 'Icon', entry['datalength'], entry['data'])
        for entry in self._custom_attribute_icons.values():
            builder.add_custom_image(entry['emitted'], 'Attribute', entry['datalength'], entry['data'])
        builder._custom_entity_icon_names = {
            name: e['emitted'] for name, e in self._custom_entity_icons.items()
        }

        for ac in self._attribute_classes:
            if ac.name and ac.icon_file:
                resolved = self._resolve_icon_ref(ac.icon_file, 'Attribute')
                builder.set_att_class_icon(ac.name, resolved)
                if str(ac.icon_file) in self._custom_attribute_icons:
                    builder._used_custom_images.add(resolved)  # declared by an AC ⇒ referenced

        for dtf in self._datetime_formats:
            if dtf.name:
                builder.register_datetime_format(dtf.name, dtf.format or '')

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
            ic_file = self._resolve_icon_ref(et.icon_file, 'Icon')
            builder._entity_type_id(et.name, rep, ic_file, color_int, shade_int, et.semantic_type)
            if et.icon_file is not None and str(et.icon_file) in self._custom_entity_icons:
                builder._used_custom_images.add(ic_file)  # declared by a type ⇒ referenced

        for lt in self._link_types:
            if not lt.name:
                continue
            color_int = None
            if lt.color is not None:
                c = lt.color
                color_int = c if isinstance(c, int) else color_to_colorref(c)
            builder._link_type_id(lt.name, color_int, lt.semantic_type)

    def _build_att_class_config(self) -> Dict[str, Dict[str, Any]]:
        """Build the attribute-class config dict consumed by semantic resolution
        and the builder. Font dataclasses are passed through unchanged."""
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
        return att_class_config

    @staticmethod
    def _assemble_summary_config(s: Settings) -> Optional[Dict[str, Any]]:
        """Build the summary config (fields + origin + custom properties), or
        None when the chart carries no document metadata."""
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
        if not (summary_fields or origin_fields or custom_props):
            return None
        return {
            'fields': summary_fields,
            'origin': origin_fields,
            'custom_properties': custom_props,
        }

    def _assemble_build(self):
        """Run the full resolve/transform pipeline and return a prepared builder.

        Shared by ``_build_xml`` (non-stream) and ``_iter_xml`` (stream) so the
        large setup isn't duplicated. Does NOT serialize — the caller decides
        between ``builder.build()`` and ``builder.iter_build()``.

        Returns:
            (builder, settings, build_kwargs, errors, timer)
        """
        errors: List[str] = []
        timer = PhaseTimer("ANXChart._build_xml")
        s = self.settings

        with timer.phase("Initialize builder"):
            builder = ANXBuilder()
            builder._custom_icons_include = (
                s.extra_cfg.custom_icons_include or 'referenced'
            )
            entity_registry: Dict[str, Tuple[str, int]] = {}

        # ── Pre-register explicit type / AC / datetime-format definitions ──
        with timer.phase("Pre-register defs"):
            self._register_static_defs(builder)

        # ── Build att_class_config (needed by semantic resolution) ─────────
        with timer.phase("Build att_class_config"):
            att_class_config = self._build_att_class_config()

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

        # ── Icon map: compute per-entity icon overrides (no mutation) ─────
        _icon_overrides: Dict[str, str] = {}
        if s.extra_cfg.icon_map is not None:
            with timer.phase("Icon-map resolve"):
                _icon_overrides = apply_icon_map(self._entities, s.extra_cfg.icon_map)

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
                icon_override=_icon_overrides.get(str(entity.id)),
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
        valid_links: List[Link] = []  # filtered, aligned 1:1 with resolved_links
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

            # link_match_entity_color — lowest-precedence dynamic source. Runs
            # before intensity / categorical so they can overwrite it when set.
            if link.line_color is None and s.extra_cfg.link_match_entity_color and link.to_id in _entity_color_map:
                rl.line_color = _entity_color_map[link.to_id]

            # Auto offset — only when original link had no explicit offset
            if link.offset is None:
                rl.offset = _auto_offsets.get(i, 0)

            resolved_links.append(rl)
            valid_links.append(link)
        timer.record(f"Link resolve ({len(self._links)})", time.perf_counter() - _t0_links)

        # ── Link styling (intensity then categorical so categorical wins) ─
        _styling = s.extra_cfg.styling
        _link_styling = getattr(_styling, 'links', None) if _styling is not None else None
        if _link_styling is not None:
            with timer.phase("Link styling (intensity)"):
                apply_link_intensity(
                    resolved_links, valid_links,
                    getattr(_link_styling, 'intensity', None),
                )
            with timer.phase("Link styling (categorical)"):
                apply_link_categorical(
                    resolved_links, valid_links,
                    getattr(_link_styling, 'categorical', None),
                )

        # ── Apply grade defaults to resolved links ─────────────────────
        with timer.phase("Grade defaults (links)"):
            resolve_grade_names(resolved_links, _grade_resolve_specs)
            apply_grade_defaults(resolved_links, _grade_params)

        # ── Store resolved links for lazy emit in build() ───────────────
        builder._resolved_items.extend(resolved_links)

        # ── Display synthesizer expansion ───────────────────────────────
        # Must run after both entity AND link resolution and before
        # builder.build() consumes att_class_config. Attribute siblings are
        # expanded first so a synthesized AC could (in principle) be
        # referenced by a label source.
        with timer.phase("Display synthesizer expansion"):
            from .transforms import (
                expand_display_attributes,
                expand_display_labels,
            )
            expand_display_attributes(
                resolved_entities,
                resolved_links,
                self.settings.extra_cfg.display_attribute,
                self._attribute_classes,
                builder,
                att_class_config,
            )
            expand_display_labels(
                resolved_entities,
                resolved_links,
                self.settings.extra_cfg.display_label,
                self._attribute_classes,
            )

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
            # Auto-generated styling legend rows (intensity/categorical with legend=true)
            if _styling is not None:
                legend_items.extend(generate_styling_legend(
                    _styling, valid_links, self._attribute_classes,
                ))

        # Build palette dicts for the builder
        palette_dicts: Optional[List[Dict[str, Any]]] = None
        if self._palettes:
            palette_dicts = [
                self._palette_to_dict(pal, full=True) for pal in self._palettes
            ]

        # ── Assemble summary config ────────────────────────────────────
        summary_config = self._assemble_summary_config(s)

        # ── Geo-map layout center offset ─────────────────────────────────
        _layout_center = (0, 0)
        if _geo_bbox != (0, 0, 0, 0):
            # Place unmatched entities below the geo-positioned bounding box
            _layout_center = (
                (_geo_bbox[0] + _geo_bbox[2]) // 2,  # center X of geo area
                _geo_bbox[3] + 200,                    # below geo area + margin
            )

        build_kwargs: Dict[str, Any] = dict(
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
        return builder, s, build_kwargs, errors, timer

    def _build_xml(self, compact: bool = False) -> Tuple[str, List[str]]:
        """Build the ANX XML (non-stream), collecting validation errors without
        raising.

        ``compact`` drops indentation (newlines kept) — used by the streaming
        parity tests. Default ``False`` preserves the pretty output that
        ``to_xml()``/``to_anx()`` return and the golden digest pins.

        Returns:
            (xml_string, errors) — errors is empty when all data is valid.
        """
        builder, s, build_kwargs, errors, timer = self._assemble_build()
        with timer.phase("builder.build()"):
            xml_str = builder.build(s, compact=compact, **build_kwargs)
        timer.summary(
            extra=f"Entities: {len(self._entities)}, Links: {len(self._links)}",
            sub_timings=[("builder.build()", builder._build_timer)],
        )
        return xml_str, errors

    def _iter_xml(self, compact: bool = True) -> Iterator[str]:
        """Stream the ANX XML in chunks. Validation is the caller's responsibility
        (``iter_xml`` validates up front)."""
        builder, s, build_kwargs, _errors, _timer = self._assemble_build()
        yield from builder.iter_build(s, compact=compact, **build_kwargs)
