"""
Validation functions for anxwritter chart data.

Extracted from ANXChart.validate() for better modularity.
Each function validates a specific section and returns a list of error dicts.
"""
from __future__ import annotations

import math
import re
from datetime import datetime as _datetime, date as _date
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from .errors import ErrorType
from .utils import _enum_val, _is_valid_color, _validate_date, _validate_time

from .models import TimeZone

if TYPE_CHECKING:
    from .entities import _BaseEntity, ThemeLine
    from .models import (
        Card, Link, AttributeClass, Strength, LegendItem, EntityType, LinkType,
        Palette, DateTimeFormat, GradeCollection, StrengthCollection,
        SemanticEntity, SemanticLink, SemanticProperty,
    )


# ── Helper functions ─────────────────────────────────────────────────────────


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


def _infer_attr_type(val: Any) -> str:
    """Infer attribute type from Python value."""
    if isinstance(val, bool):
        return 'Flag'
    if isinstance(val, (int, float)):
        return 'Number'
    # date catches both datetime.datetime and datetime.date (datetime is a subclass).
    if isinstance(val, _date):
        return 'DateTime'
    return 'Text'


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


# ── Focused validation functions ─────────────────────────────────────────────


def validate_strength_collection(
    strengths: 'StrengthCollection',
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
            errors.append({
                'type': ErrorType.DUPLICATE_NAME.value,
                'message': f"Duplicate Strength name '{st.name}' "
                           f"(first at {seen_names[st.name]})",
                'location': loc,
            })
        else:
            seen_names[st.name] = loc

    return errors


def validate_grade_collections(
    grades_one: 'GradeCollection',
    grades_two: 'GradeCollection',
    grades_three: 'GradeCollection',
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
            errors.append({
                'type': ErrorType.INVALID_GRADE_DEFAULT.value,
                'message': (
                    f"{gkey}.default = '{gc.default}' not found "
                    f"in {gkey}.items: {gc.items}"
                ),
            })

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

        # Check date/time/strength/grades
        check_date(entity.date, loc, errors)
        check_time(entity.time, loc, errors)
        check_strength(entity.strength, strength_names, loc, errors)
        check_grade(entity.grade_one, 'grade_one', gc1_items, loc, errors)
        check_grade(entity.grade_two, 'grade_two', gc2_items, loc, errors)
        check_grade(entity.grade_three, 'grade_three', gc3_items, loc, errors)
        check_attr_types(entity.attributes, loc, attr_types, errors)
        check_timezone(entity.timezone, bool(entity.date), bool(entity.time), loc, errors)

        # Inline cards: validate date/time/grades so YAML mistakes (e.g.
        # unquoted ``time: 14:30:00`` parsing as int) surface as a clean
        # invalid_time error rather than crashing the builder downstream.
        for ci, card in enumerate(entity.cards or []):
            cloc = f"{loc}.cards[{ci}]"
            check_date(card.date, cloc, errors)
            check_time(card.time, cloc, errors)
            check_grade(card.grade_one, 'grade_one', gc1_items, cloc, errors)
            check_grade(card.grade_two, 'grade_two', gc2_items, cloc, errors)
            check_grade(card.grade_three, 'grade_three', gc3_items, cloc, errors)
            check_timezone(card.timezone, bool(card.date), bool(card.time), cloc, errors)

        # Check datetime_format is registered
        if entity.datetime_format and entity.datetime_format not in dtf_names:
            errors.append({
                'type': 'unregistered_datetime_format',
                'message': f"datetime_format '{entity.datetime_format}' is not registered "
                           f"in the DateTimeFormatCollection. ANB 9 only accepts registered "
                           f"format names - use add_datetime_format() to register it first.",
                'location': loc,
            })

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

        # Check date/time/strength/grades
        check_date(link.date, loc, errors)
        check_time(link.time, loc, errors)
        check_strength(link.strength, strength_names, loc, errors)
        check_grade(link.grade_one, 'grade_one', gc1_items, loc, errors)
        check_grade(link.grade_two, 'grade_two', gc2_items, loc, errors)
        check_grade(link.grade_three, 'grade_three', gc3_items, loc, errors)
        check_attr_types(link.attributes, loc, attr_types, errors)
        check_timezone(link.timezone, bool(link.date), bool(link.time), loc, errors)

        # Inline cards: validate date/time/grades (same rationale as entities).
        for ci, card in enumerate(link.cards or []):
            cloc = f"{loc}.cards[{ci}]"
            check_date(card.date, cloc, errors)
            check_time(card.time, cloc, errors)
            check_grade(card.grade_one, 'grade_one', gc1_items, cloc, errors)
            check_grade(card.grade_two, 'grade_two', gc2_items, cloc, errors)
            check_grade(card.grade_three, 'grade_three', gc3_items, cloc, errors)
            check_timezone(card.timezone, bool(card.date), bool(card.time), cloc, errors)

        # Check datetime_format is registered
        if link.datetime_format and link.datetime_format not in dtf_names:
            errors.append({
                'type': 'unregistered_datetime_format',
                'message': f"datetime_format '{link.datetime_format}' is not registered "
                           f"in the DateTimeFormatCollection. ANB 9 only accepts registered "
                           f"format names - use add_datetime_format() to register it first.",
                'location': loc,
            })

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
) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Validate entity types and return errors and name→location map."""
    errors: List[Dict[str, Any]] = []
    et_names: Dict[str, str] = {}

    for i, et in enumerate(entity_types):
        loc = f"entity_types[{i}]"
        if not et.name:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': "Missing required field 'name' on EntityType",
                'location': loc,
            })
        elif et.name in et_names:
            errors.append({
                'type': ErrorType.DUPLICATE_NAME.value,
                'message': f"Duplicate EntityType name '{et.name}' "
                           f"(first at {et_names[et.name]})",
                'location': loc,
            })
        else:
            et_names[et.name] = loc
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

    return errors, et_names


def validate_link_types(
    link_types: List['LinkType'],
) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Validate link types and return errors and name→location map."""
    errors: List[Dict[str, Any]] = []
    lt_names: Dict[str, str] = {}

    for i, lt in enumerate(link_types):
        loc = f"link_types[{i}]"
        if not lt.name:
            errors.append({
                'type': ErrorType.MISSING_REQUIRED.value,
                'message': "Missing required field 'name' on LinkType",
                'location': loc,
            })
        elif lt.name in lt_names:
            errors.append({
                'type': ErrorType.DUPLICATE_NAME.value,
                'message': f"Duplicate LinkType name '{lt.name}' "
                           f"(first at {lt_names[lt.name]})",
                'location': loc,
            })
        else:
            lt_names[lt.name] = loc
        check_color(lt.color, 'color', loc, errors)

    return errors, lt_names


def validate_datetime_formats(
    datetime_formats: List['DateTimeFormat'],
) -> tuple[List[Dict[str, Any]], Set[str]]:
    """Validate datetime formats and return errors and name set."""
    errors: List[Dict[str, Any]] = []
    dtf_names: Dict[str, str] = {}

    for i, dtf in enumerate(datetime_formats):
        loc = f"datetime_formats[{i}]"
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

    for i, ac in enumerate(attribute_classes):
        loc = f"attribute_classes[{i}]"
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
            continue

        ac_type = _enum_val(ac.type).lower()
        if ac_type not in _MERGE_VALID:
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

    # Warn about LN-style semantic_type names (common mistake)
    all_semantic_refs = []
    for et in entity_types:
        if et.semantic_type:
            all_semantic_refs.append((et.semantic_type, f'EntityType({et.name})'))
    for lt in link_types:
        if lt.semantic_type:
            all_semantic_refs.append((lt.semantic_type, f'LinkType({lt.name})'))
    for ac in attribute_classes:
        if ac.semantic_type:
            all_semantic_refs.append((ac.semantic_type, f'AttributeClass({ac.name})'))

    for ref, loc in all_semantic_refs:
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
