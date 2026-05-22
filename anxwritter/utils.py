"""
Shared utility functions for anxwritter.
"""
import math
from datetime import datetime as _datetime, date as _date, time as _time
from typing import Any, Optional

from .colors import is_color


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


# ── Value coercion (shared by chart loading + validation) ────────────────────


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
    """Infer the i2 attribute type ('Flag'/'Number'/'DateTime'/'Text') from a value."""
    if isinstance(val, bool):
        return 'Flag'
    if isinstance(val, (int, float)):
        return 'Number'
    # date catches both datetime.datetime and datetime.date (datetime is a subclass).
    if isinstance(val, _date):
        return 'DateTime'
    return 'Text'


# ── Date / time validation ───────────────────────────────────────────────────

_DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%Y%m%d')
_TIME_FORMATS = ('%H:%M:%S', '%H:%M:%S.%f', '%H:%M', '%I:%M %p')


def _is_valid_color(val: Any) -> bool:
    """Backwards-compatible alias for :func:`anxwritter.colors.is_color`.

    Kept importable from ``anxwritter.utils`` (tests and validators rely on this
    path); the implementation lives in ``colors`` alongside ``coerce_color``.
    """
    return is_color(val)


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
