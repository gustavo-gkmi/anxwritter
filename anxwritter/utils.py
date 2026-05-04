"""
Shared utility functions for anxwritter.
"""
import math
import re
from datetime import datetime as _datetime, date as _date, time as _time
from typing import Any

from .colors import NAMED_COLORS, _NAMED_COLORS_NORM, color_to_colorref, _normalize_name


def _enum_val(x: Any) -> str:
    """Extract string value from enum or passthrough string.

    Handles both enum instances (which have a .value attribute) and plain
    strings (from YAML/JSON input). This pattern is used throughout the
    codebase to normalize enum values before mapping to ANB XML strings.

    Args:
        x: An enum instance or string value.

    Returns:
        The string value (enum.value if enum, str(x) otherwise).
    """
    if x is None:
        return ''
    return x.value if hasattr(x, 'value') else str(x)


# ── Color / date / time validation ───────────────────────────────────────────

# Case-insensitive / punctuation-insensitive lookup. NAMED_COLORS keys are
# Title Case (e.g. 'Blue', 'Light Orange') so direct lookup misses 'blue',
# 'BLUE', 'light_orange'. We delegate to colors._NAMED_COLORS_NORM which is
# the same dict colors.color_to_colorref uses internally.

_DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%Y%m%d')
_TIME_FORMATS = ('%H:%M:%S', '%H:%M:%S.%f', '%H:%M', '%I:%M %p')


# Resolution order: None → enum unwrap → bool reject → int range → float range → normalized name → hex → fallback color_to_colorref
def _is_valid_color(val: Any) -> bool:
    """Return True if val is a recognisable color (None, enum, name, hex, or int)."""
    if val is None:
        return True
    # Unwrap Color enum (or any str-Enum) first
    if hasattr(val, 'value'):
        val = val.value
    # bool is a subclass of int — must reject before int branch
    if isinstance(val, bool):
        return False
    if isinstance(val, int):
        return 0 <= val <= 0xFFFFFF
    if isinstance(val, float):
        if math.isnan(val):
            return False
        return 0 <= val <= 0xFFFFFF
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return False
        if _normalize_name(s) in _NAMED_COLORS_NORM:
            return True
        if s.startswith('#') and len(s) == 7:
            try:
                int(s[1:], 16)
                return True
            except ValueError:
                pass
        try:
            color_to_colorref(s)
            return True
        except (ValueError, TypeError):
            pass
    return False


def _validate_date(val: Any) -> bool:
    """Return True if val is a date we can serialize.

    Accepts a Python ``datetime.date`` / ``datetime.datetime`` (typical for
    YAML's auto-parsed date literals or Python users passing a typed value),
    or a string in any of the supported formats: ``yyyy-MM-dd`` (canonical),
    ``dd/mm/yyyy``, ``yyyymmdd``.  Ambiguous US ``mm/dd/yyyy`` is
    intentionally rejected.
    """
    # date covers both date and datetime (datetime is a subclass).
    if isinstance(val, _date):
        return True
    if not isinstance(val, str):
        return False
    s = val.strip()
    if not s:
        return False
    for fmt in _DATE_FORMATS:
        try:
            _datetime.strptime(s, fmt)
            return True
        except ValueError:
            continue
    return False


def _validate_time(val: Any) -> bool:
    """Return True if val is a time we can serialize.

    Accepts a Python ``datetime.time`` / ``datetime.datetime`` or a string
    in any of the supported formats: ``HH:MM:SS`` (canonical),
    ``HH:MM:SS.ffffff`` (microseconds), ``HH:MM`` (no seconds),
    ``HH:MM AM/PM`` (12-hour).
    """
    if isinstance(val, (_time, _datetime)):
        return True
    if not isinstance(val, str):
        return False
    s = val.strip()
    if not s:
        return False
    for fmt in _TIME_FORMATS:
        try:
            _datetime.strptime(s, fmt)
            return True
        except ValueError:
            continue
    return False
