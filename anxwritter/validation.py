"""
Validation functions for anxwritter chart data.

Extracted from ANXChart.validate() for better modularity.
Each function validates a specific section and returns a list of error dicts.
"""
from __future__ import annotations

import math
import re
from datetime import datetime as _datetime
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING

from .errors import ErrorType
from .utils import (
    _enum_val, _infer_attr_type, _int_or_none, _is_valid_color,
    _str_or_none, _validate_date, _validate_time,
)

from .models import TimeZone


_STRFTIME_PROBE_DT = _datetime(2024, 1, 15, 14, 30, 45, 123000)


def _is_valid_strftime(fmt: str) -> bool:
    """Return True if ``fmt`` is a strftime format string that runs cleanly."""
    if not isinstance(fmt, str) or not fmt:
        return False
    try:
        _STRFTIME_PROBE_DT.strftime(fmt)
        return True
    except (ValueError, TypeError):
        return False

if TYPE_CHECKING:
    from .entities import _BaseEntity
    from .models import (
        Card, Link, AttributeClass, LegendItem, EntityType, LinkType,
        Palette, DateTimeFormat, GradeCollection, StrengthCollection,
        SemanticEntity, SemanticLink, SemanticProperty,
    )


# ── Helper functions ─────────────────────────────────────────────────────────


# ── Checker functions (used by multiple validators) ──────────────────────────


def check_color(
    val: Any,
    col_name: str,
    loc: str,
    errors: List[Dict[str, Any]],
) -> None:
    """Validate a color value and append error if invalid."""
    if val is None:
        return
    if isinstance(val, float) and math.isnan(val):
        return
    if not _is_valid_color(val):
        errors.append({
            'type': ErrorType.UNKNOWN_COLOR.value,
            'message': f"'{col_name}' value {val!r} is not a valid color",
            'location': loc,
        })


def check_date(val: Any, loc: str, errors: List[Dict[str, Any]]) -> None:
    """Validate a date value and append error if invalid."""
    if val is None:
        return
    # Typed date / datetime values are accepted directly — _validate_date now
    # recognises both.  Don't stringify first; str(datetime(...)) produces a
    # space-separated form that no string parser accepts.
    from datetime import date as _date_cls
    if isinstance(val, _date_cls):
        return
    s = _str_or_none(val)
    if s and not _validate_date(s):
        errors.append({
            'type': ErrorType.INVALID_DATE.value,
            'message': f"Date '{s}' is not a valid date "
                       f"(supported: yyyy-MM-dd, dd/MM/yyyy, yyyymmdd)",
            'location': loc,
        })


def check_time(val: Any, loc: str, errors: List[Dict[str, Any]]) -> None:
    """Validate a time value and append error if invalid."""
    if val is None:
        return
    from datetime import time as _time_cls, datetime as _dt_cls
    if isinstance(val, (_time_cls, _dt_cls)):
        return
    s = _str_or_none(val)
    if s and not _validate_time(s):
        errors.append({
            'type': ErrorType.INVALID_TIME.value,
            'message': f"Time '{s}' is not a valid time "
                       f"(supported: HH:MM:SS, HH:MM:SS.ffffff, HH:MM, HH:MM AM/PM)",
            'location': loc,
        })


def check_strength(
    val: Any,
    strength_names: Set[str],
    loc: str,
    errors: List[Dict[str, Any]],
) -> None:
    """Validate a strength name and append error if unregistered."""
    s = _str_or_none(val)
    if s and s not in strength_names:
        errors.append({
            'type': ErrorType.INVALID_STRENGTH.value,
            'message': f"Strength '{s}' not found in chart.strengths",
            'location': loc,
        })


def check_grade(
    val: Any,
    grade_name: str,
    items: List[str],
    loc: str,
    errors: List[Dict[str, Any]],
) -> None:
    """Validate a grade reference and append error if invalid.

    Accepts either:
    - an integer (or digit string) — checked against ``items`` length, like before
    - a non-digit string — looked up in ``items``; emits ``unknown_grade`` if absent

    ``items`` is the ``GradeCollection.items`` list (used for both range checks and
    name resolution). Empty/None list disables both checks.
    """
    if val is None:
        return
    if isinstance(val, bool):
        # bool is a subclass of int in Python, but treating True/False as grade
        # indices is almost always a user mistake.
        errors.append({
            'type': ErrorType.UNKNOWN_GRADE.value,
            'message': f"'{grade_name}' got bool {val!r}; expected an integer "
                       f"index or a grade name",
            'location': loc,
        })
        return

    max_len = len(items) if items else 0

    # Integer (or digit string) → range check
    if isinstance(val, int) or _int_or_none(val) is not None:
        idx = val if isinstance(val, int) else _int_or_none(val)
        if idx is not None:
            if idx < 0:
                errors.append({
                    'type': ErrorType.GRADE_OUT_OF_RANGE.value,
                    'message': f"'{grade_name}' index {idx} is negative",
                    'location': loc,
                })
            elif max_len > 0 and idx >= max_len:
                errors.append({
                    'type': ErrorType.GRADE_OUT_OF_RANGE.value,
                    'message': f"'{grade_name}' index {idx} out of range "
                               f"(collection has {max_len} entries)",
                    'location': loc,
                })
        return

    # Non-digit string → name lookup against grade items
    name = _str_or_none(val)
    if name is None:
        return
    if not items:
        errors.append({
            'type': ErrorType.UNKNOWN_GRADE.value,
            'message': f"'{grade_name}'={name!r} but no grades are defined on the chart",
            'location': loc,
        })
        return
    if name not in items:
        errors.append({
            'type': ErrorType.UNKNOWN_GRADE.value,
            'message': f"'{grade_name}'={name!r} not found in chart.{grade_name}.items "
                       f"({', '.join(repr(i) for i in items)})",
            'location': loc,
        })


def check_timezone(
    tz: Any,
    has_date: bool,
    has_time: bool,
    loc: str,
    errors: List[Dict[str, Any]],
) -> None:
    """Validate a timezone (TimeZone dataclass or dict) and append errors if malformed."""
    if tz is None:
        return
    # Handle TimeZone dataclass
    if isinstance(tz, TimeZone):
        tz_id = tz.id
        tz_name = tz.name
    elif isinstance(tz, dict):
        tz_id = tz.get('id')
        tz_name = tz.get('name')
    else:
        errors.append({
            'type': ErrorType.INVALID_TIMEZONE.value,
            'message': f"timezone must be a TimeZone dataclass or dict with 'id' (int) and 'name' (str), "
                       f"got {type(tz).__name__}",
            'location': loc,
        })
        return
    if tz_id is None:
        errors.append({
            'type': ErrorType.INVALID_TIMEZONE.value,
            'message': "timezone missing required 'id' (int 1-122)",
            'location': loc,
        })
    elif not isinstance(tz_id, int) or tz_id < 1 or tz_id > 122:
        errors.append({
            'type': ErrorType.INVALID_TIMEZONE.value,
            'message': f"timezone 'id' must be an integer 1-122, got {tz_id!r}",
            'location': loc,
        })
    if tz_name is None or (isinstance(tz_name, str) and not tz_name.strip()):
        errors.append({
            'type': ErrorType.INVALID_TIMEZONE.value,
            'message': "timezone missing required 'name' (non-empty string)",
            'location': loc,
        })
    if not has_date or not has_time:
        errors.append({
            'type': ErrorType.TIMEZONE_WITHOUT_DATETIME.value,
            'message': "timezone requires both 'date' and 'time' to be set - "
                       "ANB ignores timezone when TimeSet='false'",
            'location': loc,
        })


def check_attr_types(
    attrs: Any,
    loc: str,
    attr_types: Dict[str, str],
    errors: List[Dict[str, Any]],
) -> None:
    """Validate attribute type consistency and update attr_types dict."""
    if attrs is None or not isinstance(attrs, dict):
        return
    for name, val in attrs.items():
        if val is None:
            continue
        if isinstance(val, float) and math.isnan(val):
            continue
        inferred = _infer_attr_type(val)
        if name in attr_types:
            if attr_types[name] != inferred:
                errors.append({
                    'type': ErrorType.TYPE_CONFLICT.value,
                    'message': f"Attribute '{name}' used as '{inferred}' "
                               f"but previously seen as '{attr_types[name]}'",
                    'location': loc,
                })
        else:
            attr_types[name] = inferred


def _check_inline_cards(cards, loc, gc1_items, gc2_items, gc3_items, errors):
    """Validate date/time/grades/timezone on an item's inline cards."""
    for ci, card in enumerate(cards or []):
        cloc = f"{loc}.cards[{ci}]"
        check_date(card.date, cloc, errors)
        check_time(card.time, cloc, errors)
        check_grade(card.grade_one, 'grade_one', gc1_items, cloc, errors)
        check_grade(card.grade_two, 'grade_two', gc2_items, cloc, errors)
        check_grade(card.grade_three, 'grade_three', gc3_items, cloc, errors)
        check_timezone(card.timezone, bool(card.date), bool(card.time), cloc, errors)


def _check_chart_item_common(item, *, loc, strength_names, dtf_names,
                             gc1_items, gc2_items, gc3_items, attr_types, errors):
    """Validate the date/time/strength/grade/attribute/timezone/datetime_format
    fields shared by entities and links, plus their inline cards.

    Field-name compatible across ``_BaseEntity`` and ``Link``; preserves the
    original per-item error ordering (item fields → inline cards →
    datetime_format registration check)."""
    check_date(item.date, loc, errors)
    check_time(item.time, loc, errors)
    check_strength(item.strength, strength_names, loc, errors)
    check_grade(item.grade_one, 'grade_one', gc1_items, loc, errors)
    check_grade(item.grade_two, 'grade_two', gc2_items, loc, errors)
    check_grade(item.grade_three, 'grade_three', gc3_items, loc, errors)
    check_attr_types(item.attributes, loc, attr_types, errors)
    check_timezone(item.timezone, bool(item.date), bool(item.time), loc, errors)

    _check_inline_cards(item.cards, loc, gc1_items, gc2_items, gc3_items, errors)

    if item.datetime_format and item.datetime_format not in dtf_names:
        errors.append({
            'type': 'unregistered_datetime_format',
            'message': f"datetime_format '{item.datetime_format}' is not registered "
                       f"in the DateTimeFormatCollection. ANB 9 only accepts registered "
                       f"format names - use add_datetime_format() to register it first.",
            'location': loc,
        })


# ── Focused validation functions ─────────────────────────────────────────────


def _attach_source(
    err: Dict[str, Any],
    sources: Optional[Dict[str, str]],
    name: Optional[str],
) -> Dict[str, Any]:
    """Attach a ``source`` key to *err* when *sources* has an entry for *name*.

    Single helper to keep the optional-source pattern out of every validator
    body. Mutates *err* in place and returns it for chaining.
    """
    if sources is None or not name:
        return err
    src = sources.get(name)
    if src is not None:
        err['source'] = src
    return err


def _tag_rows_source(errors: List[Dict[str, Any]], row_start: int,
                     sources: Optional[Dict[str, str]], name: Optional[str]) -> None:
    """Tag every error appended since ``row_start`` with the row's config source.

    The range counterpart of :func:`_attach_source`, shared by the named-registry
    validators so a row's color / behaviour errors carry the same provenance as
    its missing/duplicate-name error."""
    if not sources or not name:
        return
    src = sources.get(name)
    if src is None:
        return
    for err in errors[row_start:]:
        err.setdefault('source', src)


def _register_name(name: Optional[str], kind: str, loc: str,
                   seen: Dict[str, str], errors: List[Dict[str, Any]]) -> None:
    """Missing/duplicate-name skeleton shared by the simple named registries.

    Emits ``missing_required`` (no name) or ``duplicate_name`` (already in
    ``seen``); otherwise records ``seen[name] = loc``."""
    if not name:
        errors.append({
            'type': ErrorType.MISSING_REQUIRED.value,
            'message': f"Missing required field 'name' on {kind}",
            'location': loc,
        })
    elif name in seen:
        errors.append({
            'type': ErrorType.DUPLICATE_NAME.value,
            'message': f"Duplicate {kind} name '{name}' (first at {seen[name]})",
            'location': loc,
        })
    else:
        seen[name] = loc


def validate_strength_collection(
    strengths: 'StrengthCollection',
    sources: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Validate StrengthCollection default and items."""
    errors: List[Dict[str, Any]] = []
    strength_names = {st.name for st in strengths.items if st.name}

    # Validate default references an existing name
    if strengths.default is not None:
        if strengths.default not in strength_names:
            errors.append({
                'type': ErrorType.INVALID_STRENGTH_DEFAULT.value,
                'message': (
                    f"strengths.default = '{strengths.default}' not found "
                    f"in registered strengths: {sorted(strength_names)}"
                ),
            })

    # Validate no duplicate names
    seen_names: Dict[str, str] = {}
    for i, st in enumerate(strengths.items):
        loc = f"strengths[{i}]"
        if not st.name:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': "Missing required field 'name' on Strength",
                'location': loc,
            })
        elif st.name in seen_names:
            errors.append(_attach_source({
                'type': ErrorType.DUPLICATE_NAME.value,
                'message': f"Duplicate Strength name '{st.name}' "
                           f"(first at {seen_names[st.name]})",
                'location': loc,
            }, sources, st.name))
        else:
            seen_names[st.name] = loc

    return errors


def validate_grade_collections(
    grades_one: 'GradeCollection',
    grades_two: 'GradeCollection',
    grades_three: 'GradeCollection',
    section_sources: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Validate GradeCollection defaults exist in items."""
    errors: List[Dict[str, Any]] = []

    from .models import GradeCollection

    for gkey, gc in (
        ('grades_one', grades_one),
        ('grades_two', grades_two),
        ('grades_three', grades_three),
    ):
        if not isinstance(gc, GradeCollection):
            continue
        if gc.default is not None and gc.default not in gc.items:
            err = {
                'type': ErrorType.INVALID_GRADE_DEFAULT.value,
                'message': (
                    f"{gkey}.default = '{gc.default}' not found "
                    f"in {gkey}.items: {gc.items}"
                ),
            }
            if section_sources:
                src = section_sources.get(gkey)
                if src is not None:
                    err['source'] = src
            errors.append(err)

    return errors


def validate_entities(
    entities: List['_BaseEntity'],
    strength_names: Set[str],
    dtf_names: Set[str],
    gc1_items: List[str],
    gc2_items: List[str],
    gc3_items: List[str],
    attr_types: Dict[str, str],
) -> tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, type]]:
    """Validate entity list and return errors, entity_ids map, and entity_classes map."""
    errors: List[Dict[str, Any]] = []
    all_entity_ids: Dict[str, str] = {}
    entity_classes: Dict[str, type] = {}

    for i, entity in enumerate(entities):
        loc = f"entities[{i}] ({type(entity).__name__})"
        eid = entity.id if entity.id else None

        if not eid:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': "Missing required field 'id'",
                'location': loc,
            })
            continue

        if not entity.type:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': f"Missing required field 'type' on entity '{eid}'",
                'location': loc,
            })

        entity_classes[eid] = type(entity)

        if eid in all_entity_ids:
            errors.append({
                'type': ErrorType.DUPLICATE_ID.value,
                'message': f"Duplicate entity id '{eid}' "
                           f"(first seen at {all_entity_ids[eid]})",
                'location': loc,
            })
        else:
            all_entity_ids[eid] = loc

        # Check color fields
        check_color(getattr(entity, 'color', None), 'color', loc, errors)
        check_color(entity.label_font.color, 'label_font.color', loc, errors)
        check_color(entity.label_font.bg_color, 'label_font.bg_color', loc, errors)
        for ck in ('bg_color', 'line_color', 'shade_color'):
            check_color(getattr(entity, ck, None), ck, loc, errors)
        frame_obj = getattr(entity, 'frame', None)
        if frame_obj is not None:
            check_color(frame_obj.color, 'frame.color', loc, errors)

        _check_chart_item_common(
            entity, loc=loc, strength_names=strength_names, dtf_names=dtf_names,
            gc1_items=gc1_items, gc2_items=gc2_items, gc3_items=gc3_items,
            attr_types=attr_types, errors=errors,
        )

    return errors, all_entity_ids, entity_classes


_VALID_ARROWS = {
    'ArrowOnHead', 'ArrowOnTail', 'ArrowOnBoth',  # full ANB names
    'head', 'tail', 'both',                        # short aliases
    '->', '<-', '<->',                              # symbol aliases
}

_VALID_MULT = {
    'MultiplicityMultiple', 'MultiplicitySingle', 'MultiplicityDirected',
    'multiple', 'single', 'directed',
}

_VALID_TW = {
    'KeepsAtEventHeight', 'ReturnsToThemeHeight', 'GoesToNextEventHeight', 'NoDiversion',
    'keep_event', 'return_theme', 'next_event', 'no_diversion',
}


def validate_links(
    links: List['Link'],
    all_entity_ids: Dict[str, str],
    entity_classes: Dict[str, type],
    strength_names: Set[str],
    dtf_names: Set[str],
    gc1_items: List[str],
    gc2_items: List[str],
    gc3_items: List[str],
    attr_types: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Validate links and return errors."""
    errors: List[Dict[str, Any]] = []

    # Import ThemeLine for ordered link validation
    from .entities import ThemeLine

    for i, link in enumerate(links):
        loc = f"links[{i}]"
        from_id = link.from_id if link.from_id else None
        to_id = link.to_id if link.to_id else None

        if not from_id or not to_id:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': "Missing required field 'from_id' or 'to_id'",
                'location': loc,
            })
            continue

        if from_id == to_id:
            errors.append({
                'type': ErrorType.SELF_LOOP.value,
                'message': f"Self-loop: from_id and to_id are both '{from_id}'",
                'location': loc,
            })
            continue

        if from_id not in all_entity_ids:
            errors.append({
                'type': ErrorType.MISSING_ENTITY.value,
                'message': f"Entity '{from_id}' (from_id) not found in any entity list",
                'location': loc,
            })
        if to_id not in all_entity_ids:
            errors.append({
                'type': ErrorType.MISSING_ENTITY.value,
                'message': f"Entity '{to_id}' (to_id) not found in any entity list",
                'location': loc,
            })

        # Check colors
        check_color(link.line_color, 'line_color', loc, errors)
        check_color(link.label_font.color, 'label_font.color', loc, errors)
        check_color(link.label_font.bg_color, 'label_font.bg_color', loc, errors)

        # Check arrow style
        if link.arrow and link.arrow not in _VALID_ARROWS:
            errors.append({
                'type': ErrorType.INVALID_ARROW.value,
                'message': f"arrow '{link.arrow}' is not valid. "
                           f"Use: {', '.join(sorted(_VALID_ARROWS))}",
                'location': loc,
            })

        _check_chart_item_common(
            link, loc=loc, strength_names=strength_names, dtf_names=dtf_names,
            gc1_items=gc1_items, gc2_items=gc2_items, gc3_items=gc3_items,
            attr_types=attr_types, errors=errors,
        )

        # Check connection style enums
        mult_val = _enum_val(link.multiplicity) if link.multiplicity else None
        tw_val = _enum_val(link.theme_wiring) if link.theme_wiring else None
        if mult_val is not None and mult_val not in _VALID_MULT:
            errors.append({
                'type': ErrorType.INVALID_MULTIPLICITY.value,
                'message': f"multiplicity '{mult_val}' is not valid. "
                           f"Use: {', '.join(sorted(_VALID_MULT))}",
                'location': loc,
            })
        if tw_val is not None and tw_val not in _VALID_TW:
            errors.append({
                'type': ErrorType.INVALID_THEME_WIRING.value,
                'message': f"theme_wiring '{tw_val}' is not valid. "
                           f"Use: {', '.join(sorted(_VALID_TW))}",
                'location': loc,
            })

        # Check ordered requires both ends to be ThemeLine
        if link.ordered:
            from_cls = entity_classes.get(from_id)
            to_cls = entity_classes.get(to_id)
            if from_cls is not ThemeLine or to_cls is not ThemeLine:
                errors.append({
                    'type': ErrorType.INVALID_ORDERED.value,
                    'message': "ordered=True requires both ends to be ThemeLine entities",
                    'location': loc,
                })

    return errors


def validate_connection_conflicts(links: List['Link']) -> List[Dict[str, Any]]:
    """Validate that links between the same pair don't have conflicting connection styles."""
    errors: List[Dict[str, Any]] = []

    # Check if any link has connection fields set
    any_conn = any(
        link.multiplicity is not None or link.fan_out is not None or link.theme_wiring is not None
        for link in links
    )
    if not any_conn:
        return errors

    pair_first: Dict[tuple, tuple[tuple, int]] = {}
    for i, link in enumerate(links):
        m = _enum_val(link.multiplicity) if link.multiplicity else None
        t = _enum_val(link.theme_wiring) if link.theme_wiring else None
        style = (m, link.fan_out, t)
        if not any(v is not None for v in style):
            continue
        fid = link.from_id or ''
        tid = link.to_id or ''
        if not fid or not tid:
            continue
        pair = tuple(sorted((fid, tid)))
        if pair not in pair_first:
            pair_first[pair] = (style, i)
        elif style != pair_first[pair][0]:
            prev_style, prev_i = pair_first[pair]
            errors.append({
                'type': ErrorType.CONNECTION_CONFLICT.value,
                'message': f"Links between '{pair[0]}' and '{pair[1]}' have "
                           f"conflicting connection style: "
                           f"links[{prev_i}] sets {prev_style}, "
                           f"links[{i}] sets {style}",
                'location': f"links[{i}]",
            })

    return errors


def validate_loose_cards(
    loose_cards: List['Card'],
    all_entity_ids: Dict[str, str],
    link_ids: Set[str],
) -> List[Dict[str, Any]]:
    """Validate loose cards target existing entities/links."""
    errors: List[Dict[str, Any]] = []

    for i, card in enumerate(loose_cards):
        loc = f"loose_cards[{i}]"
        if card.entity_id and card.entity_id not in all_entity_ids:
            errors.append({
                'type': ErrorType.MISSING_TARGET.value,
                'message': f"Loose card targets entity_id '{card.entity_id}' "
                           f"which does not exist",
                'location': loc,
            })
        if card.link_id and card.link_id not in link_ids:
            errors.append({
                'type': ErrorType.MISSING_TARGET.value,
                'message': f"Loose card targets link_id '{card.link_id}' "
                           f"which does not match any Link.link_id",
                'location': loc,
            })

    return errors


# Both Title Case (legacy) and lowercase enum values are accepted.
_VALID_LEGEND_TYPES = {
    'Font', 'Text', 'Icon', 'Attribute', 'Line', 'Link', 'TimeZone', 'IconFrame',
    'font', 'text', 'icon', 'attribute', 'line', 'link', 'timezone', 'icon_frame',
}


def validate_legend_items(legend_items: List['LegendItem']) -> List[Dict[str, Any]]:
    """Validate legend items have required fields and valid types."""
    errors: List[Dict[str, Any]] = []

    for i, li in enumerate(legend_items):
        loc = f"legend_items[{i}]"
        if not li.name:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': "Missing required field 'name' on LegendItem",
                'location': loc,
            })
        # Normalize enum / case before checking
        raw = li.item_type
        type_str = _enum_val(raw) if hasattr(raw, 'value') else str(raw) if raw is not None else ''
        if type_str and type_str not in _VALID_LEGEND_TYPES and type_str.lower() not in _VALID_LEGEND_TYPES:
            errors.append({
                'type': ErrorType.INVALID_LEGEND_TYPE.value,
                'message': f"Invalid item_type '{li.item_type}'. "
                           f"Valid types: {', '.join(sorted(_VALID_LEGEND_TYPES))}",
                'location': loc,
            })

    return errors


def validate_entity_types(
    entity_types: List['EntityType'],
    sources: Optional[Dict[str, str]] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Validate entity types and return errors and name→location map."""
    errors: List[Dict[str, Any]] = []
    et_names: Dict[str, str] = {}

    # Record error count before each row so post-emitted errors (color, etc.)
    # get tagged with the row's source as well.
    for i, et in enumerate(entity_types):
        loc = f"entity_types[{i}]"
        row_start = len(errors)
        _register_name(et.name, 'EntityType', loc, et_names, errors)
        check_color(et.color, 'color', loc, errors)
        check_color(et.shade_color, 'shade_color', loc, errors)

        # Check for unsupported OLE_OBJECT representation
        if et.representation:
            rep_lower = str(et.representation).lower().replace('_', '')
            if rep_lower in ('oleobject', 'ole', 'representasole'):
                errors.append({
                    'type': ErrorType.UNSUPPORTED_REPRESENTATION.value,
                    'message': f"Representation 'OLE_OBJECT' on EntityType '{et.name}' is not yet supported. "
                               f"Use 'icon', 'box', 'circle', 'theme_line', 'event_frame', 'text_block', or 'label'.",
                    'location': loc,
                })

        # Tag every error emitted for this row with the source, if known.
        _tag_rows_source(errors, row_start, sources, et.name)

    return errors, et_names


def validate_link_types(
    link_types: List['LinkType'],
    sources: Optional[Dict[str, str]] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Validate link types and return errors and name→location map."""
    errors: List[Dict[str, Any]] = []
    lt_names: Dict[str, str] = {}

    for i, lt in enumerate(link_types):
        loc = f"link_types[{i}]"
        row_start = len(errors)
        _register_name(lt.name, 'LinkType', loc, lt_names, errors)
        check_color(lt.color, 'color', loc, errors)

        _tag_rows_source(errors, row_start, sources, lt.name)

    return errors, lt_names


def validate_datetime_formats(
    datetime_formats: List['DateTimeFormat'],
    sources: Optional[Dict[str, str]] = None,
) -> tuple[List[Dict[str, Any]], Set[str]]:
    """Validate datetime formats and return errors and name set."""
    errors: List[Dict[str, Any]] = []
    dtf_names: Dict[str, str] = {}

    for i, dtf in enumerate(datetime_formats):
        loc = f"datetime_formats[{i}]"
        row_start = len(errors)
        if not dtf.name:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': "Missing required field 'name' on DateTimeFormat",
                'location': loc,
            })
        elif len(dtf.name) > 250:
            errors.append({
                'type': 'invalid_value',
                'message': "DateTimeFormat name exceeds 250 characters",
                'location': loc,
            })
        elif dtf.name in dtf_names:
            errors.append({
                'type': ErrorType.DUPLICATE_NAME.value,
                'message': f"Duplicate DateTimeFormat name '{dtf.name}' "
                           f"(first at {dtf_names[dtf.name]})",
                'location': loc,
            })
        else:
            dtf_names[dtf.name] = loc
        if dtf.format and len(dtf.format) > 259:
            errors.append({
                'type': 'invalid_value',
                'message': "DateTimeFormat format string exceeds 259 characters",
                'location': loc,
            })

        _tag_rows_source(errors, row_start, sources, dtf.name)

    return errors, set(dtf_names.keys())


# Canonical short-name resolution for merge/paste behaviour values.
# Accepts short names ('xor'), legacy mixed-case ANB names ('AttMergeXOR'),
# and canonical ANB names ('AttMergeXor').
_BEHAVIOUR_SHORT: Dict[str, str] = {
    'assign': 'assign', 'attmergeassign': 'assign',
    'noop': 'noop', 'attmergenoop': 'noop',
    'add': 'add', 'attmergeadd': 'add',
    'add_space': 'add_space', 'attmergeaddwithspace': 'add_space',
    'add_line_break': 'add_line_break', 'attmergeaddwithlinebreak': 'add_line_break',
    'max': 'max', 'attmergemax': 'max',
    'min': 'min', 'attmergemin': 'min',
    'subtract': 'subtract', 'attmergesubtract': 'subtract',
    'subtract_swap': 'subtract_swap', 'attmergesubtractswap': 'subtract_swap',
    'or': 'or', 'attmergeor': 'or',
    'and': 'and', 'attmergeand': 'and',
    'xor': 'xor', 'attmergexor': 'xor',
}

# Per-type validity (short names). DateTime == AttTime in ANB.
_MERGE_VALID: Dict[str, Set[str]] = {
    'text':     {'add', 'add_space', 'add_line_break'},
    'number':   {'add', 'max', 'min'},
    'datetime': {'min', 'max'},
    'flag':     {'or', 'and', 'xor'},
}
_PASTE_VALID: Dict[str, Set[str]] = {
    'text':     {'add', 'add_space', 'add_line_break', 'assign', 'noop'},
    'number':   {'add', 'max', 'min', 'subtract', 'subtract_swap', 'assign', 'noop'},
    'datetime': {'min', 'max', 'assign', 'noop'},
    'flag':     {'or', 'and', 'xor', 'assign', 'noop'},
}


def validate_attribute_classes(
    attribute_classes: List['AttributeClass'],
    attr_types: Optional[Dict[str, str]] = None,
    sources: Optional[Dict[str, str]] = None,
) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Validate attribute classes and return errors and name→location map.

    Checks:
    - ``name`` is present and unique (missing_required / duplicate_name).
    - ``type`` is present on every explicit declaration (missing_required).
      anxwritter does not infer the type of a declared AttributeClass from
      data — users must state it explicitly.
    - ``merge_behaviour`` / ``paste_behaviour`` are valid for the declared
      type per ``_MERGE_VALID`` / ``_PASTE_VALID``.
    - ``ac.type`` matches the first-seen type inferred from any entity/link
      attribute with the same name (type_conflict). ``attr_types`` is the
      name→type dict populated by :func:`check_attr_types` during entity
      and link validation; keys are in capitalized form (``'Text'``,
      ``'Number'``, ``'Flag'``, ``'DateTime'``).

    Data-vs-data type conflicts (one row using a name as text, another as
    number) are caught upstream by :func:`check_attr_types`; this function
    does not re-walk entity/link attributes.
    """
    errors: List[Dict[str, Any]] = []
    ac_names: Dict[str, str] = {}
    data_types = attr_types or {}

    def _row_tag(name: Optional[str], row_start: int) -> None:
        """Apply the per-row source tag to every error appended since row_start."""
        _tag_rows_source(errors, row_start, sources, name)

    for i, ac in enumerate(attribute_classes):
        loc = f"attribute_classes[{i}]"
        row_start = len(errors)
        if not ac.name:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': "Missing required field 'name' on AttributeClass",
                'location': loc,
            })
            continue
        if ac.name in ac_names:
            errors.append({
                'type': ErrorType.DUPLICATE_NAME.value,
                'message': f"Duplicate AttributeClass name '{ac.name}' "
                           f"(first at {ac_names[ac.name]})",
                'location': loc,
            })
            _row_tag(ac.name, row_start)
            continue
        ac_names[ac.name] = loc

        if ac.type is None:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': (
                    f"AttributeClass '{ac.name}' must declare 'type' "
                    f"(one of: text, number, datetime, flag)"
                ),
                'location': f"{loc}.type",
            })
            _row_tag(ac.name, row_start)
            continue

        ac_type = _enum_val(ac.type).lower()
        if ac_type not in _MERGE_VALID:
            _row_tag(ac.name, row_start)
            continue

        inferred = data_types.get(ac.name)
        if inferred and inferred.lower() != ac_type:
            errors.append({
                'type': ErrorType.TYPE_CONFLICT.value,
                'message': (
                    f"AttributeClass '{ac.name}' declares type '{ac_type}' "
                    f"but data infers '{inferred.lower()}'"
                ),
                'location': f"{loc}.type",
            })

        for field, valid_map, err_type in (
            ('merge_behaviour', _MERGE_VALID, ErrorType.INVALID_MERGE_BEHAVIOUR),
            ('paste_behaviour', _PASTE_VALID, ErrorType.INVALID_PASTE_BEHAVIOUR),
        ):
            raw = getattr(ac, field, None)
            if raw is None:
                continue
            short = _BEHAVIOUR_SHORT.get(_enum_val(raw).lower())
            if short is None:
                errors.append({
                    'type': err_type.value,
                    'message': f"AttributeClass '{ac.name}' has unknown {field} "
                               f"'{raw}'",
                    'location': loc,
                })
                continue
            if short not in valid_map[ac_type]:
                errors.append({
                    'type': err_type.value,
                    'message': f"AttributeClass '{ac.name}' ({ac_type}) has "
                               f"invalid {field} '{raw}'. Valid for "
                               f"{ac_type}: {sorted(valid_map[ac_type])}",
                    'location': loc,
                })

        # ── Rule: datetime + visible=True is always rejected ────────────
        # ANB v9 does not render datetime values on the canvas after import;
        # the surrounding chrome appears but the value is blank. Users must
        # set visible=False and configure an extra_cfg.display_attribute entry
        # that references this AC to render the formatted date as a paired
        # text sibling.
        if ac_type == 'datetime' and ac.visible is True:
            errors.append({
                'type': ErrorType.DATETIME_AC_FORBIDS_VISIBLE.value,
                'message': (
                    f"AttributeClass '{ac.name}' (datetime) cannot have "
                    f"visible=True: ANB v9 does not render datetime values "
                    f"on the canvas, so the chrome would render with no "
                    f"value. Set visible=False and add an "
                    f"extra_cfg.display_attribute entry with a "
                    f"'{{d:%Y-%m-%d}}'-style template referencing this AC to "
                    f"render the formatted date as a paired text sibling."
                ),
                'location': f"{loc}.visible",
            })

        _row_tag(ac.name, row_start)

    return errors, ac_names


def validate_palettes(
    palettes: List['Palette'],
    et_names: Dict[str, str],
    lt_names: Dict[str, str],
    ac_names: Dict[str, str],
    attribute_classes: List['AttributeClass'],
    entities: List['_BaseEntity'],
    links: List['Link'],
) -> List[Dict[str, Any]]:
    """Validate palettes reference valid types and classes."""
    errors: List[Dict[str, Any]] = []

    # Build sets of attribute classes not allowed in palettes
    ac_no_add: Set[str] = set()
    ac_not_user: Set[str] = set()
    for ac in attribute_classes:
        if ac.name and ac.user_can_add is False:
            ac_no_add.add(ac.name)
        if ac.name and ac.is_user is False:
            ac_not_user.add(ac.name)

    # Build a map of attribute class names -> explicit type for value checking.
    # Canonicalise to Title Case so explicit declarations match the same
    # comparison strings ('Number'/'Flag'/'DateTime') that the inference
    # branch below already produces. _enum_val returns the lowercase enum
    # value (e.g. 'number'); without canonicalisation the downstream
    # comparisons silently never matched and palette_type_mismatch was
    # never raised for explicit AttributeClass declarations.
    _AC_TYPE_TITLE = {'text': 'Text', 'number': 'Number',
                      'flag': 'Flag', 'datetime': 'DateTime'}
    ac_type_map: Dict[str, str] = {}
    for ac in attribute_classes:
        if ac.name and ac.type is not None:
            raw = _enum_val(ac.type).lower()
            ac_type_map[ac.name] = _AC_TYPE_TITLE.get(raw, raw)
    # Also infer types from entity/link attributes
    for ent in entities:
        for attr_name, attr_val in (ent.attributes or {}).items():
            if attr_name not in ac_type_map:
                if isinstance(attr_val, bool):
                    ac_type_map[attr_name] = 'Flag'
                elif isinstance(attr_val, (int, float)):
                    ac_type_map[attr_name] = 'Number'
                elif isinstance(attr_val, str):
                    ac_type_map[attr_name] = 'Text'
    for lnk in links:
        for attr_name, attr_val in (lnk.attributes or {}).items():
            if attr_name not in ac_type_map:
                if isinstance(attr_val, bool):
                    ac_type_map[attr_name] = 'Flag'
                elif isinstance(attr_val, (int, float)):
                    ac_type_map[attr_name] = 'Number'
                elif isinstance(attr_val, str):
                    ac_type_map[attr_name] = 'Text'

    for i, pal in enumerate(palettes):
        loc = f"palettes[{i}]"
        for et_name in pal.entity_types:
            if et_name not in et_names:
                errors.append({
                    'type': 'palette_unknown_ref',
                    'message': f"Palette '{pal.name}' references unknown entity type '{et_name}'",
                    'location': loc,
                })
        for lt_name in pal.link_types:
            if lt_name not in lt_names:
                errors.append({
                    'type': 'palette_unknown_ref',
                    'message': f"Palette '{pal.name}' references unknown link type '{lt_name}'",
                    'location': loc,
                })
        for ac_name in pal.attribute_classes:
            if ac_name not in ac_names:
                errors.append({
                    'type': 'palette_unknown_ref',
                    'message': f"Palette '{pal.name}' references unknown attribute class '{ac_name}'",
                    'location': loc,
                })
            elif ac_name in ac_not_user:
                errors.append({
                    'type': 'palette_invalid_class',
                    'message': (
                        f"Palette '{pal.name}' references attribute class '{ac_name}' "
                        f"which has is_user=False - ANB rejects palette entries "
                        f"for non-user classes"
                    ),
                    'location': loc,
                })
            elif ac_name in ac_no_add:
                errors.append({
                    'type': 'palette_invalid_class',
                    'message': (
                        f"Palette '{pal.name}' references attribute class '{ac_name}' "
                        f"which has user_can_add=False - ANB rejects palette entries "
                        f"for non-user-add classes"
                    ),
                    'location': loc,
                })
        for j, ae in enumerate(pal.attribute_entries):
            ae_loc = f"{loc}.attribute_entries[{j}]"
            if not ae.name:
                errors.append({
                    'type': ErrorType.MISSING_REQUIRED.value,
                    'message': "Missing required field 'name' on PaletteAttributeEntry",
                    'location': ae_loc,
                })
            elif ae.name in ac_not_user:
                errors.append({
                    'type': 'palette_invalid_class',
                    'message': (
                        f"Palette '{pal.name}' attribute entry '{ae.name}' "
                        f"has is_user=False - ANB rejects palette entries "
                        f"for non-user classes"
                    ),
                    'location': ae_loc,
                })
            elif ae.name in ac_no_add:
                errors.append({
                    'type': 'palette_invalid_class',
                    'message': (
                        f"Palette '{pal.name}' attribute entry '{ae.name}' "
                        f"has user_can_add=False - ANB rejects palette entries "
                        f"for non-user-add classes"
                    ),
                    'location': ae_loc,
                })
            if ae.value is not None and ae.name in ac_type_map:
                ac_type = ac_type_map[ae.name]
                val = str(ae.value)
                if ac_type == 'Number':
                    try:
                        float(val)
                    except ValueError:
                        errors.append({
                            'type': ErrorType.PALETTE_TYPE_MISMATCH.value,
                            'message': (
                                f"Palette entry '{ae.name}' value '{val}' "
                                f"is not a valid number (attribute class type is Number)"
                            ),
                            'location': ae_loc,
                        })
                elif ac_type == 'Flag':
                    if val.lower() not in ('true', 'false'):
                        errors.append({
                            'type': ErrorType.PALETTE_TYPE_MISMATCH.value,
                            'message': (
                                f"Palette entry '{ae.name}' value '{val}' "
                                f"is not 'true'/'false' (attribute class type is Flag)"
                            ),
                            'location': ae_loc,
                        })
                elif ac_type == 'DateTime':
                    if not re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', val):
                        errors.append({
                            'type': ErrorType.PALETTE_TYPE_MISMATCH.value,
                            'message': (
                                f"Palette entry '{ae.name}' value '{val}' "
                                f"is not valid xsd:dateTime (expected YYYY-MM-DDTHH:MM:SS)"
                            ),
                            'location': ae_loc,
                        })

    return errors


_LN_PATTERN = re.compile(r'^LN(Entity|Link|Property)[A-Z]')


def validate_semantic_types(
    semantic_entities: List['SemanticEntity'],
    semantic_links: List['SemanticLink'],
    semantic_properties: List['SemanticProperty'],
    entity_types: List['EntityType'],
    link_types: List['LinkType'],
    attribute_classes: List['AttributeClass'],
    entities: Optional[List['_BaseEntity']] = None,
    links: Optional[List['Link']] = None,
) -> List[Dict[str, Any]]:
    """Validate semantic type definitions and references."""
    errors: List[Dict[str, Any]] = []

    # Validate custom semantic type definitions
    for i, se in enumerate(semantic_entities):
        loc = f'semantic_entities[{i}]'
        if not se.name:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': 'SemanticEntity missing name',
                'location': loc,
            })
        if not se.kind_of and not se.abstract:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': 'SemanticEntity missing kind_of',
                'location': loc,
            })

    for i, sl in enumerate(semantic_links):
        loc = f'semantic_links[{i}]'
        if not sl.name:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': 'SemanticLink missing name',
                'location': loc,
            })
        if not sl.kind_of and not sl.abstract:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': 'SemanticLink missing kind_of',
                'location': loc,
            })

    for i, sp in enumerate(semantic_properties):
        loc = f'semantic_properties[{i}]'
        if not sp.name:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': 'SemanticProperty missing name',
                'location': loc,
            })
        if not sp.base_property and not sp.abstract:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': 'SemanticProperty missing base_property',
                'location': loc,
            })

    # Collect every (ref, location, tree) site that emits SemanticTypeGuid.
    # tree is 'entity' | 'link' | 'property' — selects the resolver lookup
    # to check membership against for the unknown-name pass below.
    all_semantic_refs: List[tuple] = []
    for i, et in enumerate(entity_types):
        if et.semantic_type:
            all_semantic_refs.append(
                (et.semantic_type, f'entity_types[{i}].semantic_type', 'entity')
            )
    for i, lt in enumerate(link_types):
        if lt.semantic_type:
            all_semantic_refs.append(
                (lt.semantic_type, f'link_types[{i}].semantic_type', 'link')
            )
    for i, ac in enumerate(attribute_classes):
        if ac.semantic_type:
            all_semantic_refs.append(
                (ac.semantic_type, f'attribute_classes[{i}].semantic_type', 'property')
            )
    for ent in (entities or []):
        if getattr(ent, 'semantic_type', None):
            all_semantic_refs.append(
                (ent.semantic_type, f'entities[{ent.id}].semantic_type', 'entity')
            )
    for i, lk in enumerate(links or []):
        if getattr(lk, 'semantic_type', None):
            all_semantic_refs.append(
                (lk.semantic_type, f'links[{i}].semantic_type', 'link')
            )

    # LN-pattern check (i2 COM API names are always wrong)
    for ref, loc, _tree in all_semantic_refs:
        if _LN_PATTERN.match(ref):
            errors.append({
                'type': ErrorType.INVALID_SEMANTIC_TYPE.value,
                'message': (
                    f"semantic_type '{ref}' looks like an i2 COM API name (LN* pattern). "
                    f"Use the standard type name (e.g. 'Person' not 'LNEntityPerson') "
                    f"or a raw GUID (guid...)."
                ),
                'location': loc,
            })

    # Unknown-name check: every reference must be a registered name in its
    # matching tree, or a raw 'guid…' literal (passthrough, no further check).
    _tree_sets = {
        'entity': ({se.name for se in semantic_entities if se.name}, 'semantic_entities'),
        'link': ({sl.name for sl in semantic_links if sl.name}, 'semantic_links'),
        'property': ({sp.name for sp in semantic_properties if sp.name}, 'semantic_properties'),
    }
    for ref, loc, tree in all_semantic_refs:
        if ref.startswith('guid'):
            continue
        if _LN_PATTERN.match(ref):
            continue  # already flagged as INVALID_SEMANTIC_TYPE
        known, section = _tree_sets[tree]
        if ref in known:
            continue
        errors.append({
            'type': ErrorType.UNKNOWN_SEMANTIC_TYPE.value,
            'message': (
                f"semantic_type '{ref}' is not registered in {section} "
                f"and does not start with 'guid'."
            ),
            'location': loc,
        })

    return errors


# ── Geo-map validation ─────────────────────────────────────────────────────


def validate_geo_map(
    geo_map: Any,
    entities: List['_BaseEntity'],
) -> List[Dict[str, Any]]:
    """Validate geo_map configuration.

    Accepts a GeoMapCfg dataclass or a raw dict (for paths that don't
    convert to dataclass before validation).

    Returns a list of error dicts. Empty list means valid.
    """
    errors: List[Dict[str, Any]] = []
    if geo_map is None:
        return errors

    # Support both dataclass and raw dict
    def _get(attr: str, default=None):
        if isinstance(geo_map, dict):
            return geo_map.get(attr, default)
        return getattr(geo_map, attr, default)

    loc = 'settings.extra_cfg.geo_map'

    # attribute_name is required
    if not _get('attribute_name'):
        errors.append({
            'type': ErrorType.INVALID_GEO_MAP.value,
            'message': "geo_map requires 'attribute_name'",
            'location': loc,
        })

    # mode validation
    valid_modes = ('position', 'latlon', 'both')
    mode = _get('mode') or 'both'
    if mode not in valid_modes:
        errors.append({
            'type': ErrorType.INVALID_GEO_MAP.value,
            'message': f"geo_map.mode must be one of {valid_modes}, got '{mode}'",
            'location': f'{loc}.mode',
        })

    # width/height validation (for position/both modes)
    if mode in ('position', 'both'):
        w = _get('width') or 3000
        h = _get('height') or 2000
        if w <= 0:
            errors.append({
                'type': ErrorType.INVALID_GEO_MAP.value,
                'message': f"geo_map.width must be positive, got {w}",
                'location': f'{loc}.width',
            })
        if h <= 0:
            errors.append({
                'type': ErrorType.INVALID_GEO_MAP.value,
                'message': f"geo_map.height must be positive, got {h}",
                'location': f'{loc}.height',
            })

    # spread_radius
    sr = _get('spread_radius') or 0
    if sr < 0:
        errors.append({
            'type': ErrorType.INVALID_GEO_MAP.value,
            'message': f"geo_map.spread_radius must be >= 0, got {sr}",
            'location': f'{loc}.spread_radius',
        })

    # data validation
    data = _get('data') or {}
    if not data and not _get('data_file'):
        errors.append({
            'type': ErrorType.INVALID_GEO_MAP.value,
            'message': "geo_map requires 'data' or 'data_file' with at least one entry",
            'location': loc,
        })

    for key, coords in data.items():
        if not isinstance(coords, (list, tuple)) or len(coords) < 2:
            errors.append({
                'type': ErrorType.INVALID_GEO_MAP.value,
                'message': f"geo_map.data['{key}'] must be [lat, lon], got {coords!r}",
                'location': f'{loc}.data[{key}]',
            })
            continue
        lat, lon = coords[0], coords[1]
        if not (-90 <= lat <= 90):
            errors.append({
                'type': ErrorType.INVALID_GEO_MAP.value,
                'message': f"geo_map.data['{key}'] latitude {lat} out of range [-90, 90]",
                'location': f'{loc}.data[{key}]',
            })
        if not (-180 <= lon <= 180):
            errors.append({
                'type': ErrorType.INVALID_GEO_MAP.value,
                'message': f"geo_map.data['{key}'] longitude {lon} out of range [-180, 180]",
                'location': f'{loc}.data[{key}]',
            })

    return errors


# ── Styling validation (extra_cfg.styling.links.{intensity,categorical}) ────


_VALID_SCALES = ('linear', 'log', 'sqrt', 'power', 'quantile', 'threshold')
_VALID_SPACES = ('rgb', 'rgb_linear', 'hsl')
_VALID_MISSING = ('fallback', 'skip', 'error')


def _collect_numeric_attr_values(
    links: List['Link'],
    attr_name: str,
) -> tuple:
    """Return (values_seen, non_numeric_seen) for an attribute across links.

    Used to validate intensity attributes. Skips ``None`` and missing entries.
    """
    values: List[float] = []
    non_numeric: List[Any] = []
    for link in links:
        attrs = getattr(link, 'attributes', None) or {}
        if attr_name not in attrs:
            continue
        v = attrs[attr_name]
        if v is None:
            continue
        # bool is a subclass of int — reject explicitly so True doesn't count as 1.0
        if isinstance(v, bool):
            non_numeric.append(v)
            continue
        if isinstance(v, (int, float)):
            if isinstance(v, float) and math.isnan(v):
                continue
            values.append(float(v))
            continue
        non_numeric.append(v)
    return values, non_numeric


def _validate_intensity_block(
    icfg: Any,
    links: List['Link'],
    base_loc: str,
) -> List[Dict[str, Any]]:
    """Validate an IntensityCfg block. Returns list of error dicts."""
    errors: List[Dict[str, Any]] = []
    if icfg is None:
        return errors

    # Resolve effective fields for width and color (top-level shortcuts inherited).
    width = getattr(icfg, 'width', None)
    color = getattr(icfg, 'color', None)
    if width is None and color is None:
        # An IntensityCfg with neither width nor color set is a silent no-op.
        return errors

    top_attr = getattr(icfg, 'attribute', None)
    top_scale = getattr(icfg, 'scale', None)
    top_domain = getattr(icfg, 'domain', None)

    # missing policy
    missing = getattr(icfg, 'missing', None)
    if missing is not None and missing not in _VALID_MISSING:
        errors.append({
            'type': ErrorType.INVALID_INTENSITY_CONFIG.value,
            'message': f"intensity.missing must be one of {_VALID_MISSING}, got '{missing}'",
            'location': f'{base_loc}.missing',
        })

    # legend_count >= 2 if set
    lc = getattr(icfg, 'legend_count', None)
    if lc is not None and (not isinstance(lc, int) or lc < 2):
        errors.append({
            'type': ErrorType.INVALID_INTENSITY_CONFIG.value,
            'message': f"intensity.legend_count must be an int >= 2, got {lc!r}",
            'location': f'{base_loc}.legend_count',
        })

    def _check_sub(sub: Any, sub_name: str) -> None:
        sub_loc = f'{base_loc}.{sub_name}'
        attr_name = getattr(sub, 'attribute', None) or top_attr
        scale = getattr(sub, 'scale', None) or top_scale or 'sqrt'
        domain = getattr(sub, 'domain', None)
        if domain is None:
            domain = top_domain
        power = getattr(sub, 'power', None)

        if not attr_name:
            errors.append({
                'type': ErrorType.INVALID_INTENSITY_ATTRIBUTE.value,
                'message': f"intensity.{sub_name} requires 'attribute' (or top-level intensity.attribute)",
                'location': f'{sub_loc}.attribute',
            })
            return

        # scale validity
        scale_str = _enum_val(scale) if hasattr(scale, 'value') else str(scale)
        if scale_str not in _VALID_SCALES:
            errors.append({
                'type': ErrorType.INVALID_INTENSITY_CONFIG.value,
                'message': f"intensity.{sub_name}.scale must be one of {_VALID_SCALES}, got '{scale_str}'",
                'location': f'{sub_loc}.scale',
            })
            return

        # threshold is reserved for a future release.
        if scale_str == 'threshold':
            errors.append({
                'type': ErrorType.INVALID_INTENSITY_CONFIG.value,
                'message': "intensity scale 'threshold' is reserved — not implemented in v1",
                'location': f'{sub_loc}.scale',
            })

        # power scale needs a power value
        if scale_str == 'power' and (power is None or not isinstance(power, (int, float)) or power <= 0):
            errors.append({
                'type': ErrorType.INVALID_INTENSITY_CONFIG.value,
                'message': f"intensity.{sub_name}.scale='power' requires 'power' > 0",
                'location': f'{sub_loc}.power',
            })

        # domain validation — accept None, 'robust', or [min, max]
        if domain is not None and not (isinstance(domain, str) and domain == 'robust'):
            if not (isinstance(domain, (list, tuple)) and len(domain) == 2):
                errors.append({
                    'type': ErrorType.INVALID_INTENSITY_DOMAIN.value,
                    'message': f"intensity.{sub_name}.domain must be [min, max], 'robust', or omitted; got {domain!r}",
                    'location': f'{sub_loc}.domain',
                })
            else:
                a, b = domain
                if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                    errors.append({
                        'type': ErrorType.INVALID_INTENSITY_DOMAIN.value,
                        'message': f"intensity.{sub_name}.domain values must be numeric, got [{a!r}, {b!r}]",
                        'location': f'{sub_loc}.domain',
                    })
                elif a >= b:
                    errors.append({
                        'type': ErrorType.INVALID_INTENSITY_DOMAIN.value,
                        'message': f"intensity.{sub_name}.domain[0] must be < domain[1], got [{a}, {b}]",
                        'location': f'{sub_loc}.domain',
                    })

        # Attribute presence and numericity
        values, non_numeric = _collect_numeric_attr_values(links, attr_name)
        if non_numeric:
            errors.append({
                'type': ErrorType.INVALID_INTENSITY_ATTRIBUTE.value,
                'message': (
                    f"intensity.{sub_name}.attribute '{attr_name}' must be numeric on every link "
                    f"that defines it; found {len(non_numeric)} non-numeric value(s) "
                    f"(first: {non_numeric[0]!r})"
                ),
                'location': f'{sub_loc}.attribute',
            })
        # log scale needs all values > 0
        if scale_str == 'log' and values and any(v <= 0 for v in values):
            bad = [v for v in values if v <= 0]
            errors.append({
                'type': ErrorType.INVALID_INTENSITY_DOMAIN.value,
                'message': (
                    f"intensity.{sub_name}.scale='log' requires every value > 0 on attribute "
                    f"'{attr_name}'; found {len(bad)} non-positive (first: {bad[0]})"
                ),
                'location': f'{sub_loc}.attribute',
            })

        # Sub-specific checks
        if sub_name == 'width':
            rng = getattr(sub, 'range', None)
            if rng is None:
                errors.append({
                    'type': ErrorType.INVALID_INTENSITY_RANGE.value,
                    'message': "intensity.width requires 'range' [min_width, max_width]",
                    'location': f'{sub_loc}.range',
                })
            elif not (isinstance(rng, (list, tuple)) and len(rng) == 2):
                errors.append({
                    'type': ErrorType.INVALID_INTENSITY_RANGE.value,
                    'message': f"intensity.width.range must be [min, max], got {rng!r}",
                    'location': f'{sub_loc}.range',
                })
            else:
                a, b = rng
                if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                    errors.append({
                        'type': ErrorType.INVALID_INTENSITY_RANGE.value,
                        'message': f"intensity.width.range values must be numeric, got [{a!r}, {b!r}]",
                        'location': f'{sub_loc}.range',
                    })
                elif a < 0 or b < 0:
                    errors.append({
                        'type': ErrorType.INVALID_INTENSITY_RANGE.value,
                        'message': f"intensity.width.range values must be >= 0, got [{a}, {b}]",
                        'location': f'{sub_loc}.range',
                    })
                elif a >= b:
                    errors.append({
                        'type': ErrorType.INVALID_INTENSITY_RANGE.value,
                        'message': f"intensity.width.range[0] must be < range[1], got [{a}, {b}]",
                        'location': f'{sub_loc}.range',
                    })
        else:  # color
            ramp = getattr(sub, 'ramp', None)
            if ramp is None:
                errors.append({
                    'type': ErrorType.INVALID_INTENSITY_RAMP.value,
                    'message': "intensity.color requires 'ramp' with at least two colors",
                    'location': f'{sub_loc}.ramp',
                })
            elif not isinstance(ramp, (list, tuple)) or len(ramp) < 2:
                errors.append({
                    'type': ErrorType.INVALID_INTENSITY_RAMP.value,
                    'message': f"intensity.color.ramp must have at least two colors, got {ramp!r}",
                    'location': f'{sub_loc}.ramp',
                })
            else:
                for i_c, c in enumerate(ramp):
                    if not _is_valid_color(c):
                        errors.append({
                            'type': ErrorType.INVALID_INTENSITY_RAMP.value,
                            'message': f"intensity.color.ramp[{i_c}] is not a valid color: {c!r}",
                            'location': f'{sub_loc}.ramp[{i_c}]',
                        })
                        break
            space = getattr(sub, 'space', None)
            if space is not None:
                space_str = _enum_val(space) if hasattr(space, 'value') else str(space)
                if space_str not in _VALID_SPACES:
                    errors.append({
                        'type': ErrorType.INVALID_INTENSITY_CONFIG.value,
                        'message': f"intensity.color.space must be one of {_VALID_SPACES}, got '{space_str}'",
                        'location': f'{sub_loc}.space',
                    })
            diverging = getattr(sub, 'diverging', None)
            midpoint = getattr(sub, 'midpoint', None)
            if diverging and midpoint is None:
                errors.append({
                    'type': ErrorType.INVALID_INTENSITY_CONFIG.value,
                    'message': "intensity.color.diverging=true requires 'midpoint'",
                    'location': f'{sub_loc}.midpoint',
                })

    if width is not None:
        _check_sub(width, 'width')
    if color is not None:
        _check_sub(color, 'color')

    return errors


def _validate_categorical_block(
    ccfg: Any,
    links: List['Link'],
    strength_names: Set[str],
    base_loc: str,
) -> List[Dict[str, Any]]:
    """Validate a CategoricalCfg block. Returns list of error dicts."""
    errors: List[Dict[str, Any]] = []
    if ccfg is None:
        return errors

    attr_name = getattr(ccfg, 'attribute', None)
    styles = getattr(ccfg, 'styles', None) or {}
    default = getattr(ccfg, 'default', None)
    missing = getattr(ccfg, 'missing', None)

    if not attr_name:
        errors.append({
            'type': ErrorType.INVALID_CATEGORICAL_ATTRIBUTE.value,
            'message': "categorical requires 'attribute'",
            'location': f'{base_loc}.attribute',
        })
    if not styles:
        errors.append({
            'type': ErrorType.INVALID_CATEGORICAL_CONFIG.value,
            'message': "categorical requires 'styles' with at least one entry",
            'location': f'{base_loc}.styles',
        })

    if missing is not None and missing not in _VALID_MISSING:
        errors.append({
            'type': ErrorType.INVALID_CATEGORICAL_CONFIG.value,
            'message': f"categorical.missing must be one of {_VALID_MISSING}, got '{missing}'",
            'location': f'{base_loc}.missing',
        })

    def _check_style(s: Any, loc: str) -> None:
        lc = getattr(s, 'line_color', None)
        lw = getattr(s, 'line_width', None)
        strn = getattr(s, 'strength', None)
        if lc is None and lw is None and strn is None:
            errors.append({
                'type': ErrorType.INVALID_CATEGORICAL_STYLE.value,
                'message': f"categorical style at {loc} has no settable fields (line_color/line_width/strength)",
                'location': loc,
            })
        if lc is not None and not _is_valid_color(lc):
            errors.append({
                'type': ErrorType.INVALID_CATEGORICAL_STYLE.value,
                'message': f"categorical style line_color is not a valid color: {lc!r}",
                'location': f'{loc}.line_color',
            })
        if lw is not None and (not isinstance(lw, int) or lw < 0):
            errors.append({
                'type': ErrorType.INVALID_CATEGORICAL_STYLE.value,
                'message': f"categorical style line_width must be a non-negative int, got {lw!r}",
                'location': f'{loc}.line_width',
            })
        if strn is not None and strength_names and strn not in strength_names:
            errors.append({
                'type': ErrorType.INVALID_CATEGORICAL_STYLE.value,
                'message': (
                    f"categorical style strength '{strn}' is not registered "
                    f"(use chart.add_strength to declare it)"
                ),
                'location': f'{loc}.strength',
            })

    for key, st in styles.items():
        _check_style(st, f"{base_loc}.styles['{key}']")
    if default is not None:
        _check_style(default, f"{base_loc}.default")

    # If missing == 'error', surface links that don't have the attribute
    # at validate time so users get the full punch list pre-build.
    if attr_name and missing == 'error':
        for i, link in enumerate(links):
            attrs = getattr(link, 'attributes', None) or {}
            if attr_name not in attrs or attrs.get(attr_name) is None:
                errors.append({
                    'type': ErrorType.INVALID_CATEGORICAL_ATTRIBUTE.value,
                    'message': (
                        f"categorical.missing='error' and link[{i}] has no '{attr_name}' attribute"
                    ),
                    'location': f'links[{i}].attributes.{attr_name}',
                })

    return errors


def validate_styling(
    styling: Any,
    links: List['Link'],
    strength_names: Set[str],
) -> List[Dict[str, Any]]:
    """Validate ``extra_cfg.styling`` for link intensity and categorical config.

    Accepts a ``StylingCfg`` dataclass or ``None``. Returns a list of error
    dicts; empty list means valid.

    Refuses to do data-driven styling if both ``intensity`` and ``categorical``
    target the same attribute — that's ambiguous precedence the user should
    resolve in their config.
    """
    errors: List[Dict[str, Any]] = []
    if styling is None:
        return errors

    links_cfg = getattr(styling, 'links', None)
    if links_cfg is None:
        return errors

    base = 'settings.extra_cfg.styling.links'
    icfg = getattr(links_cfg, 'intensity', None)
    ccfg = getattr(links_cfg, 'categorical', None)

    errors.extend(_validate_intensity_block(icfg, links, f'{base}.intensity'))
    errors.extend(_validate_categorical_block(ccfg, links, strength_names, f'{base}.categorical'))

    # Conflict: both target the same attribute → ambiguous precedence.
    if icfg is not None and ccfg is not None:
        # Intensity attributes can come from width.attribute, color.attribute,
        # or the top-level shortcut.
        i_attrs: Set[str] = set()
        top_attr = getattr(icfg, 'attribute', None)
        if top_attr:
            i_attrs.add(top_attr)
        for sub_name in ('width', 'color'):
            sub = getattr(icfg, sub_name, None)
            if sub is not None:
                a = getattr(sub, 'attribute', None)
                if a:
                    i_attrs.add(a)
                elif top_attr:
                    i_attrs.add(top_attr)
        c_attr = getattr(ccfg, 'attribute', None)
        if c_attr and c_attr in i_attrs:
            errors.append({
                'type': ErrorType.STYLING_CONFLICT.value,
                'message': (
                    f"intensity and categorical both target attribute '{c_attr}' — "
                    f"pick one. Mixed numeric-and-lookup styling on the same attribute "
                    f"has ambiguous precedence."
                ),
                'location': base,
            })

    return errors


# ── Multi-attribute display synthesizers (attribute sibling + label) ─────────

_VALID_DISPLAY_KINDS = frozenset({'entity', 'link', 'both'})
_VALID_DISPLAY_MISSING = frozenset({'skip', 'substitute', 'error'})


def _display_kind(disp: Any) -> str:
    return str(getattr(disp, 'kind', None) or 'both').lower()


def _kinds_overlap(k1: str, k2: str) -> bool:
    """True when two ``kind`` filters could apply to the same item."""
    if k1 == 'both' or k2 == 'both':
        return True
    return k1 == k2


def _is_valid_identifier(name: str) -> bool:
    """True if ``name`` can be used as a Python format-spec field name.

    Python's ``str.format`` accepts identifier-shaped field names plus dots
    and brackets for attribute/index access. We restrict to plain
    identifiers — alias-mode requires explicit ``alias`` for anything else.
    """
    return isinstance(name, str) and name.isidentifier()


class _AnyFormatProbe:
    """Sentinel value for the validation dry-run that accepts any format
    spec without raising.

    Used when we can't statically infer the source AC's type (e.g. AC type
    is text, or AC isn't declared). The validator's job is to catch
    *template* errors, not type-mismatch errors that would only fire at
    runtime when a specific value flows through — those are surfaced
    defensively by the transform itself.
    """
    def __format__(self, format_spec):  # noqa: D401 - dunder
        return ''


def _try_format_static(template: str, sample: Dict[str, Any]) -> Optional[str]:
    """Try ``template.format_map(sample)`` and return an error message if it
    fails. Returns ``None`` on success.

    The sample dict provides values for every declared alias so a syntactic
    issue (mismatched brace, bad format spec) is the only thing that can
    raise — KeyError means "alias used in template that wasn't in sources",
    which we surface as a structural error.
    """
    try:
        template.format_map(sample)
    except KeyError as e:
        return f"template references unknown key {e!s} (no matching source alias)."
    except (ValueError, IndexError) as e:
        return f"template format error: {e!s}"
    except Exception as e:  # pragma: no cover - defensive
        return f"template raised {type(e).__name__}: {e!s}"
    return None


def _validate_display_entries(
    displays: List[Any],
    attribute_classes: List['AttributeClass'],
    entities: List['_BaseEntity'],
    links: List['Link'],
    ac_names: Dict[str, str],
    entity_type_names: Set[str],
    link_type_names: Set[str],
    *,
    family: str,
    base_loc: str,
) -> List[Dict[str, Any]]:
    """Shared validator for ``display_attribute`` / ``display_label`` entries.

    family='attribute': synthesizes a sibling AC — ``attribute_name`` is
    required, the inner ``attribute_class.name`` / ``.type`` must be ``None``,
    the synthesized name must not collide with an explicit AC, and at most one
    entry may target a given ``(kind, type, attribute_name)`` slot. Source ACs
    may be visible (the caller accepts the double-render); a visible *datetime*
    source is still rejected, but by ``DATETIME_AC_FORBIDS_VISIBLE`` in
    ``validate_attribute_classes``, not here.

    family='label': renders into the item label — no ``attribute_name`` /
    ``attribute_class`` constraint; at most one entry may apply to a given
    ``(kind, type)`` label slot.

    Common to both: required ``key`` and ``template``. ``sources`` is optional
    for a placeholder-free (static) template but required when the template
    references placeholders. Each source must reference a declared AC, ``alias``
    required for non-identifier attribute names, unique aliases per entry,
    per-source
    ``missing`` ∈ {skip, substitute, error}, a template dry-run, and a
    per-item walk for any ``missing='error'`` source. Multiple entries may
    share an ``attribute_name`` as long as their ``(kind, type)`` scopes are
    disjoint; a genuine overlap (same slot, intersecting kinds, same
    specificity tier) is a ``display_overlap_conflict``.
    """
    errors: List[Dict[str, Any]] = []
    if not displays:
        return errors

    is_attr = family == 'attribute'
    ac_by_name: Dict[str, 'AttributeClass'] = {
        ac.name: ac for ac in attribute_classes if ac.name
    }

    # Entries eligible for overlap detection: (index, kind, type, slot).
    # slot = attribute_name (attribute family) or '' (the single label slot).
    participants: list = []

    for i, disp in enumerate(displays):
        loc = f"{base_loc}[{i}]"
        key = getattr(disp, 'key', None)
        kind = _display_kind(disp)
        type_filter = getattr(disp, 'type', None)
        template = getattr(disp, 'template', None)
        sources = getattr(disp, 'sources', None) or []
        attr_name = getattr(disp, 'attribute_name', None) if is_attr else None
        inner = getattr(disp, 'attribute_class', None) if is_attr else None

        ok = True

        # key required (identity for layering / lock / delete)
        if not key:
            errors.append({
                'type': ErrorType.DISPLAY_INVALID.value,
                'message': (
                    f"{base_loc}[{i}]: 'key' is required (identity for "
                    f"config layering / lock / delete)."
                ),
                'location': f"{loc}.key",
            })
            ok = False

        # kind enum
        if kind not in _VALID_DISPLAY_KINDS:
            errors.append({
                'type': ErrorType.DISPLAY_INVALID.value,
                'message': (
                    f"{base_loc}[{i}].kind {kind!r} is not one of "
                    f"{sorted(_VALID_DISPLAY_KINDS)}."
                ),
                'location': f"{loc}.kind",
            })
            ok = False

        # `type` filter (when set) must reference a known entity/link type.
        # Scope by `kind`: 'entity' → entity types only, 'link' → link types
        # only, 'both' (default) → either. "Known" means EITHER registered
        # via add_entity_type / add_link_type OR observed on at least one
        # entity / link in the chart data (the library allows inline-typed
        # entities without pre-registration). Catches the typo case where a
        # bad type filter would otherwise silently match nothing.
        if type_filter and kind in _VALID_DISPLAY_KINDS:
            observed_entity_types = {e.type for e in entities if e.type}
            observed_link_types = {ln.type for ln in links if ln.type}
            known_entity_types = entity_type_names | observed_entity_types
            known_link_types = link_type_names | observed_link_types
            if kind == 'entity':
                resolved = type_filter in known_entity_types
                where = 'entity_types'
            elif kind == 'link':
                resolved = type_filter in known_link_types
                where = 'link_types'
            else:  # 'both' or any other valid kind treats as either
                resolved = (type_filter in known_entity_types
                            or type_filter in known_link_types)
                where = 'entity_types or link_types'
            if not resolved:
                errors.append({
                    'type': ErrorType.DISPLAY_INVALID.value,
                    'message': (
                        f"{base_loc}[{i}].type {type_filter!r} is not "
                        f"registered in {where} and no entity/link has "
                        f"this type (declare via add_entity_type / "
                        f"add_link_type, fix the typo, or omit the type "
                        f"filter)."
                    ),
                    'location': f"{loc}.type",
                })
                ok = False

        # attribute_name required (attribute family only)
        if is_attr and not attr_name:
            errors.append({
                'type': ErrorType.DISPLAY_INVALID.value,
                'message': (
                    f"display_attribute[{i}]: 'attribute_name' is required "
                    f"(names the synthesized text-sibling AttributeClass)."
                ),
                'location': f"{loc}.attribute_name",
            })
            ok = False

        # template required
        if not template or not isinstance(template, str):
            errors.append({
                'type': ErrorType.DISPLAY_INVALID.value,
                'message': (
                    f"{base_loc}[{i}]: 'template' is required and must be a "
                    f"non-empty string."
                ),
                'location': f"{loc}.template",
            })
            continue

        # Sources are optional for a placeholder-free (static) template — e.g.
        # a literal "(líq.)" label. A template that references placeholders
        # still requires sources to resolve them. Dry-running against an empty
        # mapping tells the two apart: a static template renders cleanly, a
        # placeholder (or malformed) template raises.
        if not sources:
            err_msg = _try_format_static(template, {})
            if err_msg is not None:
                errors.append({
                    'type': ErrorType.DISPLAY_INVALID.value,
                    'message': (
                        f"{base_loc}[{i}]: 'sources' is required because the "
                        f"template references placeholders — {err_msg}"
                    ),
                    'location': f"{loc}.sources",
                })
                continue
            # Static template, no sources: valid. Fall through so the entry
            # still takes part in name-collision / overlap detection.

        # Per-source checks: attribute existence, alias requirement, missing
        # enum, and (attribute family) visible=False.
        aliases_seen: Dict[str, int] = {}
        alias_sample: Dict[str, Any] = {}
        for j, src in enumerate(sources):
            attr = getattr(src, 'attribute', None)
            if not attr:
                errors.append({
                    'type': ErrorType.DISPLAY_INVALID.value,
                    'message': (
                        f"{base_loc}[{i}].sources[{j}]: 'attribute' is "
                        f"required."
                    ),
                    'location': f"{loc}.sources[{j}].attribute",
                })
                continue

            src_ac = ac_by_name.get(attr)
            if src_ac is None:
                errors.append({
                    'type': ErrorType.DISPLAY_INVALID.value,
                    'message': (
                        f"{base_loc}[{i}].sources[{j}].attribute {attr!r} "
                        f"doesn't reference any declared AttributeClass."
                    ),
                    'location': f"{loc}.sources[{j}].attribute",
                })

            alias = getattr(src, 'alias', None)
            if alias is None:
                if not _is_valid_identifier(attr):
                    errors.append({
                        'type': ErrorType.DISPLAY_INVALID.value,
                        'message': (
                            f"{base_loc}[{i}].sources[{j}]: attribute "
                            f"{attr!r} isn't a valid Python identifier, so "
                            f"'alias' is required for template substitution."
                        ),
                        'location': f"{loc}.sources[{j}].alias",
                    })
                    alias_key = None
                else:
                    alias_key = attr
            else:
                if not _is_valid_identifier(alias):
                    errors.append({
                        'type': ErrorType.DISPLAY_INVALID.value,
                        'message': (
                            f"{base_loc}[{i}].sources[{j}].alias {alias!r} "
                            f"must be a valid Python identifier."
                        ),
                        'location': f"{loc}.sources[{j}].alias",
                    })
                    alias_key = None
                else:
                    alias_key = alias

            if alias_key is not None:
                if alias_key in aliases_seen:
                    errors.append({
                        'type': ErrorType.DISPLAY_INVALID.value,
                        'message': (
                            f"{base_loc}[{i}]: alias {alias_key!r} used by "
                            f"sources[{aliases_seen[alias_key]}] and "
                            f"sources[{j}]."
                        ),
                        'location': f"{loc}.sources[{j}].alias",
                    })
                else:
                    aliases_seen[alias_key] = j
                    src_type = (
                        _enum_val(src_ac.type).lower()
                        if src_ac is not None and src_ac.type is not None
                        else None
                    )
                    if src_type == 'datetime':
                        alias_sample[alias_key] = _STRFTIME_PROBE_DT
                    elif src_type in ('number',):
                        alias_sample[alias_key] = 0
                    else:
                        alias_sample[alias_key] = _AnyFormatProbe()

            # A visible source AC is allowed: the caller accepts the
            # double-render (raw value + synthesized sibling), or hides the
            # source themselves. Visible *datetime* sources remain rejected
            # independently by DATETIME_AC_FORBIDS_VISIBLE in
            # validate_attribute_classes (ANB v9 can't render datetime on the
            # canvas), so no narrowing is needed here.

            missing = getattr(src, 'missing', None)
            if missing is not None and missing not in _VALID_DISPLAY_MISSING:
                errors.append({
                    'type': ErrorType.DISPLAY_INVALID.value,
                    'message': (
                        f"{base_loc}[{i}].sources[{j}].missing {missing!r} "
                        f"is not one of {sorted(_VALID_DISPLAY_MISSING)}."
                    ),
                    'location': f"{loc}.sources[{j}].missing",
                })

        # Template dry-run.
        if alias_sample:
            err_msg = _try_format_static(template, alias_sample)
            if err_msg:
                errors.append({
                    'type': ErrorType.DISPLAY_INVALID.value,
                    'message': f"{base_loc}[{i}].template: {err_msg}",
                    'location': f"{loc}.template",
                })

        # Inner attribute_class sanity (attribute family only).
        if is_attr and inner is not None:
            if getattr(inner, 'name', None):
                errors.append({
                    'type': ErrorType.DISPLAY_INVALID.value,
                    'message': (
                        f"display_attribute[{i}].attribute_class.name must "
                        f"be None — the synthesized AC is auto-named via "
                        f"'attribute_name'."
                    ),
                    'location': f"{loc}.attribute_class.name",
                })
            if getattr(inner, 'type', None) is not None:
                errors.append({
                    'type': ErrorType.DISPLAY_INVALID.value,
                    'message': (
                        f"display_attribute[{i}].attribute_class.type must "
                        f"be None — the synthesized AC is auto-typed as text."
                    ),
                    'location': f"{loc}.attribute_class.type",
                })

        # Eligible for overlap detection once it has identity + slot.
        if ok and (not is_attr or attr_name):
            participants.append((i, kind, type_filter, attr_name if is_attr else ''))

    # Name-collision pass (attribute family): synthesized name vs explicit AC.
    # NOTE: multiple entries sharing an attribute_name is intentional (one
    # formatter per type) — overlap detection handles same-slot ties instead.
    if is_attr:
        explicit = dict(ac_names)
        for i, disp in enumerate(displays):
            sib_name = getattr(disp, 'attribute_name', None)
            if sib_name and sib_name in explicit:
                errors.append({
                    'type': ErrorType.DISPLAY_NAME_COLLISION.value,
                    'message': (
                        f"display_attribute[{i}] synthesized AC name "
                        f"{sib_name!r} collides with explicit AttributeClass "
                        f"at {explicit[sib_name]}."
                    ),
                    'location': f"{base_loc}[{i}].attribute_name",
                })

    # Overlap pass — same slot, intersecting kinds, same specificity tier.
    n = len(participants)
    for a in range(n):
        ia, ka, ta, slota = participants[a]
        for b in range(a + 1, n):
            ib, kb, tb, slotb = participants[b]
            if slota != slotb or not _kinds_overlap(ka, kb):
                continue
            same_tier = (ta is None and tb is None) or (
                ta is not None and tb is not None and ta == tb
            )
            if not same_tier:
                continue  # typed beats untyped, or disjoint types
            slot_desc = f"attribute {slota!r}" if slota else "the label"
            errors.append({
                'type': ErrorType.DISPLAY_OVERLAP_CONFLICT.value,
                'message': (
                    f"{base_loc}[{ib}] overlaps {base_loc}[{ia}]: both apply "
                    f"to {slot_desc} for kind={kb!r} type={tb!r}. Scope them "
                    f"to disjoint types, or merge them into one entry."
                ),
                'location': f"{base_loc}[{ib}]",
            })

    # Per-item walk for any source with missing='error'.
    for i, disp in enumerate(displays):
        sources = getattr(disp, 'sources', None) or []
        for j, src in enumerate(sources):
            if getattr(src, 'missing', None) != 'error':
                continue
            attr = getattr(src, 'attribute', None)
            if not attr:
                continue
            for kind, items in (('entities', entities), ('links', links)):
                for k, it in enumerate(items):
                    attrs = getattr(it, 'attributes', None) or {}
                    if attr not in attrs or attrs[attr] is None:
                        errors.append({
                            'type': ErrorType.DISPLAY_INVALID.value,
                            'message': (
                                f"{base_loc}[{i}].sources[{j}].missing="
                                f"'error' and {kind}[{k}] has no {attr!r} "
                                f"attribute."
                            ),
                            'location': f"{kind}[{k}].attributes.{attr}",
                        })

    return errors


def validate_display_attribute(
    displays: List[Any],
    attribute_classes: List['AttributeClass'],
    entities: List['_BaseEntity'],
    links: List['Link'],
    ac_names: Dict[str, str],
    entity_type_names: Set[str],
    link_type_names: Set[str],
) -> List[Dict[str, Any]]:
    """Validate ``extra_cfg.display_attribute`` entries (sibling-AC family)."""
    return _validate_display_entries(
        displays, attribute_classes, entities, links, ac_names,
        entity_type_names, link_type_names,
        family='attribute', base_loc='settings.extra_cfg.display_attribute',
    )


def validate_display_label(
    displays: List[Any],
    attribute_classes: List['AttributeClass'],
    entities: List['_BaseEntity'],
    links: List['Link'],
    ac_names: Dict[str, str],
    entity_type_names: Set[str],
    link_type_names: Set[str],
) -> List[Dict[str, Any]]:
    """Validate ``extra_cfg.display_label`` entries (label-target family)."""
    return _validate_display_entries(
        displays, attribute_classes, entities, links, ac_names,
        entity_type_names, link_type_names,
        family='label', base_loc='settings.extra_cfg.display_label',
    )
