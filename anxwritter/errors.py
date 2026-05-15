"""Validation errors for anxwritter chart data."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List


class ErrorType(str, Enum):
    """Validation error type strings.

    Central registry of all error types used by validate(). Using this enum
    prevents typos and enables IDE autocomplete in tests.
    """
    # Required field errors
    MISSING_REQUIRED = 'missing_required'

    # Duplicate errors
    DUPLICATE_ID = 'duplicate_id'
    DUPLICATE_NAME = 'duplicate_name'

    # Reference errors
    MISSING_ENTITY = 'missing_entity'
    MISSING_TARGET = 'missing_target'

    # Format/value errors
    UNKNOWN_COLOR = 'unknown_color'
    INVALID_DATE = 'invalid_date'
    INVALID_TIME = 'invalid_time'
    TYPE_CONFLICT = 'type_conflict'
    INVALID_ARROW = 'invalid_arrow'
    SELF_LOOP = 'self_loop'

    # Strength errors
    INVALID_STRENGTH = 'invalid_strength'
    INVALID_STRENGTH_DEFAULT = 'invalid_strength_default'

    # Grade errors
    INVALID_GRADE_DEFAULT = 'invalid_grade_default'
    GRADE_OUT_OF_RANGE = 'grade_out_of_range'
    UNKNOWN_GRADE = 'unknown_grade'

    # Ordered link errors
    INVALID_ORDERED = 'invalid_ordered'

    # Legend errors
    INVALID_LEGEND_TYPE = 'invalid_legend_type'

    # Timezone errors
    INVALID_TIMEZONE = 'invalid_timezone'
    TIMEZONE_WITHOUT_DATETIME = 'timezone_without_datetime'

    # Connection errors
    INVALID_MULTIPLICITY = 'invalid_multiplicity'
    INVALID_THEME_WIRING = 'invalid_theme_wiring'
    CONNECTION_CONFLICT = 'connection_conflict'

    # Config errors
    CONFIG_CONFLICT = 'config_conflict'

    # Palette errors
    PALETTE_TYPE_MISMATCH = 'palette_type_mismatch'

    # Representation errors
    UNSUPPORTED_REPRESENTATION = 'unsupported_representation'

    # Datetime format errors
    INVALID_DATETIME_FORMAT = 'invalid_datetime_format'

    # Semantic type errors
    INVALID_SEMANTIC_TYPE = 'invalid_semantic_type'
    UNKNOWN_SEMANTIC_TYPE = 'unknown_semantic_type'

    # Attribute class behaviour errors
    INVALID_MERGE_BEHAVIOUR = 'invalid_merge_behaviour'
    INVALID_PASTE_BEHAVIOUR = 'invalid_paste_behaviour'

    # Geo-map errors
    INVALID_GEO_MAP = 'invalid_geo_map'


class ANXValidationError(Exception):
    """Raised when chart data contains validation errors.

    Attributes:
        errors: List of structured error dicts.

    The error dict shape — ``type``, ``location``, ``message`` — is the
    stable contract. The optional ``source`` key (and ``config_source`` on
    ``config_conflict`` errors) identifies the config layer that contributed
    the offending entry; present only when the entry was applied via
    :meth:`ANXChart.apply_config` / :meth:`ANXChart.apply_config_file` with a
    known ``source_name``. The string returned by ``str(exc)`` is intentionally
    NOT a stable contract — match on the dict keys, not the formatted message.
    """

    def __init__(self, errors: List[Dict[str, Any]]) -> None:
        self.errors = errors
        msg = f"{len(errors)} validation error(s) in chart data:\n" + \
              "\n".join(_format_error_line(e) for e in errors)
        super().__init__(msg)


def _format_error_line(err: Dict[str, Any]) -> str:
    """Format one error dict for the ANXValidationError message body.

    Appends a ``(source: X)`` suffix when ``err`` has a ``source`` key, or a
    ``(config source: X)`` suffix for ``config_conflict`` errors carrying
    ``config_source``. Message-string format is documented as unstable —
    callers should consume the dict keys, not parse this output.
    """
    line = f"  - [{err['type']}] {err['message']}"
    src = err.get('source') or err.get('config_source')
    if src:
        label = 'config source' if 'config_source' in err and 'source' not in err else 'source'
        line += f" ({label}: {src})"
    return line
